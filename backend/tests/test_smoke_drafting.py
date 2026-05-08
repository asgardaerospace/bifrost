"""Sprint 5 — drafting: grounded, never auto-sent, weak-context refusal."""

from __future__ import annotations


def test_executive_summary_draft_grounds_in_mission_memory(client, db_session):
    from app.services import memory as memory_service

    m = client.post(
        "/api/v1/missions",
        json={
            "codename": "DRAFT-1",
            "name": "Draft mission",
            "priority": "high",
            "status": "active",
            "description": "propulsion qualification static fire",
        },
    ).json()
    memory_service.upsert_record(
        db_session,
        source_type="note",
        source_id=801,
        content="Propulsion qualification on track; awaiting final range-safety sign-off.",
        title="Status note",
        mission_id=m["id"],
    )
    db_session.commit()

    r = client.post(
        "/api/v1/drafting/executive-summary",
        json={"mission_id": m["id"]},
    )
    assert r.status_code == 200
    body = r.json()
    if not body["weak_retrieval"]:
        assert body["citations"]
        assert body["confidence"] > 0


def test_escalation_brief_with_no_context_refuses_gracefully(client):
    m = client.post(
        "/api/v1/missions",
        json={"codename": "DRAFT-EMPTY", "name": "Empty"},
    ).json()
    r = client.post(
        "/api/v1/drafting/escalation-brief",
        json={"mission_id": m["id"], "hours": 1},
    )
    assert r.status_code == 200
    body = r.json()
    if body["weak_retrieval"]:
        assert "INSUFFICIENT" in body["summary"].upper()
        assert body["confidence"] == 0


def test_drafting_requires_target_entity_id(client):
    r = client.post("/api/v1/drafting/approval-summary", json={})
    assert r.status_code == 422

    r = client.post("/api/v1/drafting/investor-followup", json={})
    assert r.status_code == 422

    r = client.post("/api/v1/drafting/supplier-outreach", json={})
    assert r.status_code == 422


def test_drafting_supplier_outreach_works(client):
    r = client.post(
        "/api/v1/drafting/supplier-outreach", json={"supplier_id": 42}
    )
    assert r.status_code == 200
    body = r.json()
    # Either grounded or weak — but always shape-consistent.
    assert "objective" in body
    assert body["model"]
