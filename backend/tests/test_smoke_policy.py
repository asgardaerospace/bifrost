"""Sprint 8 — execution policy registry + governance enforcement."""

from __future__ import annotations

from app.services import policy as policy_service


def test_policy_catalog_present():
    pols = policy_service.list_policies()
    keys = {p.action_type for p in pols}
    assert "queue_item_complete" in keys
    assert "agent_recommend_action" in keys
    assert "communication_send" in keys


def test_evaluate_denies_below_confidence_floor(client, db_session):
    decision = policy_service.evaluate(
        db_session,
        action_type="agent_recommend_action",
        confidence=0.1,
        mission_id=None,
        actor="test",
    )
    assert decision.allow is False
    assert decision.reason == "below_confidence_floor"


def test_evaluate_allows_above_floor(client, db_session):
    decision = policy_service.evaluate(
        db_session,
        action_type="agent_autonomous_observe",
        confidence=0.99,
        mission_id=None,
        actor="test",
    )
    assert decision.allow is True
    assert decision.requires_approval is False


def test_evaluate_unknown_action_denies(client, db_session):
    decision = policy_service.evaluate(
        db_session,
        action_type="not_a_real_action_type_xyz",
        confidence=1.0,
        mission_id=None,
        actor="test",
    )
    assert decision.allow is False
    assert decision.reason == "unknown_action_type"


def test_governance_audit_endpoint(client):
    # Trigger at least one decision via the policy engine.
    r = client.get("/api/v1/governance/policies")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 3


def test_policy_lookup_endpoint(client):
    r = client.get("/api/v1/governance/policies/queue_item_complete")
    assert r.status_code == 200
    body = r.json()
    assert body["action_type"] == "queue_item_complete"
    assert body["requires_approval"] is True
