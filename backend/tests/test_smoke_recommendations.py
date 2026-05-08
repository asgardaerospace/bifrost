"""Sprint 5 — recommendations engine: idempotent, audit-grounded, decision flow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.approval import Approval
from app.models.execution_queue import ExecutionQueueItem
from app.services import operational_recommendations as rec_service


def test_regenerate_creates_route_approval_for_stale(client, db_session):
    # Stale approval (created > 24h ago).
    old = Approval(
        entity_type="generic",
        entity_id=1,
        action="execute_test",
        status="pending",
        requested_by="ops",
        created_at=datetime.now(timezone.utc) - timedelta(hours=48),
    )
    db_session.add(old)
    db_session.commit()

    report = rec_service.regenerate_all(db_session)
    assert report.created >= 1

    r = client.get(
        "/api/v1/recommendations?recommendation_type=route_approval"
    )
    assert r.status_code == 200
    body = r.json()
    assert any(rec["target_entity_id"] == old.id for rec in body)


def test_regenerate_is_idempotent(client, db_session):
    old = Approval(
        entity_type="generic",
        entity_id=2,
        action="execute_test",
        status="pending",
        requested_by="ops",
        created_at=datetime.now(timezone.utc) - timedelta(hours=48),
    )
    db_session.add(old)
    db_session.commit()

    a = rec_service.regenerate_all(db_session)
    b = rec_service.regenerate_all(db_session)
    # Second run refreshes existing rows rather than creating duplicates.
    assert b.created == 0
    assert b.refreshed >= a.created


def test_regenerate_creates_queue_reprioritize_for_overdue_low_priority(
    client, db_session
):
    # Overdue queue item at low priority.
    item = ExecutionQueueItem(
        item_type="task",
        title="Overdue low-priority task",
        status="queued",
        priority_score=20,
        due_at=datetime.now(timezone.utc) - timedelta(hours=12),
    )
    db_session.add(item)
    db_session.commit()

    rec_service.regenerate_all(db_session)

    r = client.get(
        "/api/v1/recommendations?recommendation_type=queue_reprioritize"
    )
    assert any(rec["target_entity_id"] == item.id for rec in r.json())


def test_decide_recommendation_lifecycle(client, db_session):
    # Create one recommendation via the engine.
    item = ExecutionQueueItem(
        item_type="task",
        title="Decision target",
        status="queued",
        priority_score=10,
        due_at=datetime.now(timezone.utc) - timedelta(hours=24),
    )
    db_session.add(item)
    db_session.commit()
    rec_service.regenerate_all(db_session)

    r = client.get("/api/v1/recommendations?recommendation_type=queue_reprioritize")
    rec_id = r.json()[0]["id"]

    decide = client.post(
        f"/api/v1/recommendations/{rec_id}/decide",
        json={"decision": "accepted", "decided_by": "ops@asgard.local"},
    )
    assert decide.status_code == 200
    assert decide.json()["status"] == "accepted"
    assert decide.json()["decided_by"] == "ops@asgard.local"

    # Cannot decide twice.
    second = client.post(
        f"/api/v1/recommendations/{rec_id}/decide",
        json={"decision": "dismissed", "decided_by": "ops"},
    )
    assert second.status_code == 409


def test_recommendations_carry_citations(client, db_session):
    item = ExecutionQueueItem(
        item_type="task",
        title="Citations target",
        status="queued",
        priority_score=10,
        due_at=datetime.now(timezone.utc) - timedelta(hours=24),
        summary="Mission-critical low-priority overdue task",
    )
    db_session.add(item)
    db_session.commit()
    rec_service.regenerate_all(db_session)

    r = client.get("/api/v1/recommendations?recommendation_type=queue_reprioritize")
    body = r.json()
    assert body
    rec = body[0]
    assert rec["citations"]
    assert rec["confidence"] > 0
    assert rec["rationale"]
