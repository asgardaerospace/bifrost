"""Sprint 6 — governed agents + workflow trace + governance enforcement.

Doctrine asserted by these tests:
  * agents are finite, registered, inspectable
  * every run persists an AutonomyOperation + per-stage trace rows
  * agents NEVER mutate state directly — they stage ProposedAction rows
  * proposed actions are approval-gated by default
  * an agent cannot propose actions outside its allowed_actions
  * orchestrator finalizes weak runs without queueing approvals
  * handoffs only fire on explicit opt-in and within bounded edges
"""

from __future__ import annotations

import pytest

from app.models.agent_workflow import AgentWorkflowStage
from app.models.autonomy import AutonomyOperation, ProposedAction
from app.services.agents import REGISTRY, descriptors, get as get_agent
from app.services.agents.base import BaseAgent, StageContext, StageResult
from app.services.workflow_orchestrator import cancel_run, run_agent


# ---------------------------------------------------------------------------
# registry / descriptors
# ---------------------------------------------------------------------------


def test_canonical_agents_registered():
    names = set(REGISTRY.keys())
    expected = {
        "intelligence_agent",
        "supplier_risk_agent",
        "executive_briefing_agent",
        "capital_monitoring_agent",
        "mission_coordination_agent",
        "queue_coordination_agent",
    }
    assert expected.issubset(names), names


def test_descriptors_expose_governance_metadata():
    for d in descriptors():
        # Every agent must declare what it can do, what needs approval,
        # and what domains it can read.
        assert d.allowed_actions, d.name
        assert d.required_approvals, d.name
        assert d.accessible_domains, d.name
        assert d.workflow_key
        assert d.stages, d.name
        assert d.escalation_rules


def test_list_agents_endpoint(client):
    r = client.get("/api/v1/agents")
    assert r.status_code == 200, r.text
    body = r.json()
    names = {a["name"] for a in body}
    assert "intelligence_agent" in names
    assert "supplier_risk_agent" in names


def test_get_agent_descriptor_404_for_unknown(client):
    r = client.get("/api/v1/agents/nope_unknown")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# orchestrator: stage trace persistence + proposed actions
# ---------------------------------------------------------------------------


def test_running_capital_monitor_with_no_data_is_weak(db_session):
    agent = get_agent("capital_monitoring_agent")
    assert agent is not None
    result = run_agent(db_session, agent, trigger="manual:test", actor="ops")
    # No funding signals seeded → no proposed actions, weak finalization.
    assert result.proposed_action_count == 0
    assert result.final_status == "weak"
    assert result.operation.workflow_key == "capital.monitor"
    assert result.operation.trigger == "manual:test"

    # Stages were still persisted with an audit trail.
    stages = (
        db_session.query(AgentWorkflowStage)
        .filter(AgentWorkflowStage.autonomy_operation_id == result.operation.id)
        .order_by(AgentWorkflowStage.stage_index)
        .all()
    )
    assert len(stages) >= 1
    assert all(s.status == "completed" for s in stages)
    assert all(s.started_at is not None and s.completed_at is not None for s in stages)


def test_run_persists_no_proposed_actions_when_data_absent(db_session):
    agent = get_agent("queue_coordination_agent")
    result = run_agent(db_session, agent, trigger="manual", actor="ops")
    pa = (
        db_session.query(ProposedAction)
        .filter(ProposedAction.autonomy_operation_id == result.operation.id)
        .all()
    )
    assert pa == []
    assert result.final_status == "weak"


def test_run_endpoint_returns_run_report(client):
    r = client.post(
        "/api/v1/agents/capital_monitoring_agent/run",
        json={"trigger": "smoke", "propagate_handoffs": False},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["agent_name"] == "capital_monitoring_agent"
    assert body["workflow_key"] == "capital.monitor"
    assert body["final_status"] in ("proposed", "weak", "failed")
    assert "operation_id" in body
    assert body["handoff_runs"] == []  # propagate_handoffs disabled


def test_run_endpoint_404_for_unknown_agent(client):
    r = client.post(
        "/api/v1/agents/nope/run",
        json={"trigger": "smoke"},
    )
    assert r.status_code == 404


def test_workflow_trace_endpoint_returns_stages(client):
    r = client.post(
        "/api/v1/agents/queue_coordination_agent/run",
        json={"trigger": "smoke"},
    )
    op_id = r.json()["operation_id"]

    trace = client.get(f"/api/v1/agent-runs/{op_id}")
    assert trace.status_code == 200, trace.text
    body = trace.json()
    assert body["operation"]["id"] == op_id
    assert body["operation"]["agent_name"] == "queue_coordination_agent"
    assert body["operation"]["workflow_key"] == "queue.coordinate"
    assert isinstance(body["stages"], list)
    assert len(body["stages"]) >= 1
    # Stages must come back in declared order.
    indices = [s["stage_index"] for s in body["stages"]]
    assert indices == sorted(indices)
    assert body["proposed_action_count"] == 0


def test_list_agent_runs_filterable(client):
    client.post(
        "/api/v1/agents/capital_monitoring_agent/run",
        json={"trigger": "filter-test"},
    )
    r = client.get("/api/v1/agent-runs", params={"agent_name": "capital_monitoring_agent"})
    assert r.status_code == 200
    body = r.json()
    assert body
    assert all(row["agent_name"] == "capital_monitoring_agent" for row in body)


def test_workflow_trace_404_for_missing_operation(client):
    r = client.get("/api/v1/agent-runs/9999999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# governance: bounded scope, approval gating
# ---------------------------------------------------------------------------


def test_agent_cannot_propose_outside_allowed_actions(db_session):
    """An agent's stage_action() must reject any action_type that is not
    declared in `allowed_actions`. This is the core bounded-scope rule."""

    class RogueAgent(BaseAgent):
        name = "rogue_test_agent"
        version = "0.0.1"
        purpose = "test"
        allowed_actions = ("only_this",)
        required_approvals = ("only_this",)
        accessible_domains = ("test",)
        confidence_threshold = 50
        workflow_key = "rogue.test"

        def _pipeline(self):
            def stage(ctx: StageContext) -> StageResult:
                # Try to propose an action NOT in allowed_actions.
                self.stage_action(
                    ctx,
                    action_type="forbidden_action",
                    target_entity_type=None,
                    target_entity_id=None,
                    payload={},
                )
                return StageResult(output_payload={}, confidence=100)

            return [stage]

    rogue = RogueAgent()
    # Don't register globally — just run.
    result = run_agent(db_session, rogue, trigger="rogue", actor="test")
    # Stage should fail; run should finalize as failed.
    assert result.final_status == "failed"
    assert result.error and "not permitted" in result.error.lower()


def test_proposed_actions_default_to_requires_approval(db_session):
    """Every action staged by the supplied agents must end up on the
    approval-gated path. We assert this on the schema/contract side: even if
    a stage forgot to pass requires_approval=True, the base class should
    coerce based on `required_approvals`."""

    class TestAgent(BaseAgent):
        name = "approval_test_agent"
        version = "0.0.1"
        purpose = "test"
        allowed_actions = ("test_action",)
        required_approvals = ("test_action",)  # forces gate even if stage forgets
        accessible_domains = ("test",)
        confidence_threshold = 0
        workflow_key = "approval.test"

        def _pipeline(self):
            def stage(ctx: StageContext) -> StageResult:
                # Pass requires_approval=False explicitly — registry of
                # required_approvals must still enforce the gate.
                self.stage_action(
                    ctx,
                    action_type="test_action",
                    target_entity_type=None,
                    target_entity_id=None,
                    payload={"data": 1},
                    requires_approval=False,
                )
                return StageResult(output_payload={}, confidence=100)

            return [stage]

    agent = TestAgent()
    result = run_agent(db_session, agent, trigger="t", actor="ops")
    assert result.final_status == "proposed"
    actions = (
        db_session.query(ProposedAction)
        .filter(ProposedAction.autonomy_operation_id == result.operation.id)
        .all()
    )
    assert len(actions) == 1
    assert actions[0].requires_approval is True
    assert actions[0].status == "pending"


# ---------------------------------------------------------------------------
# orchestrator: cancellation + endpoint
# ---------------------------------------------------------------------------


def test_cancel_endpoint_marks_run_cancelled(client, db_session):
    r = client.post(
        "/api/v1/agents/capital_monitoring_agent/run",
        json={"trigger": "to-cancel"},
    )
    op_id = r.json()["operation_id"]
    # Force back to running so cancel applies (run finalized to 'weak' above).
    op = db_session.get(AutonomyOperation, op_id)
    op.status = "running"
    db_session.commit()

    cancel = client.post(f"/api/v1/agent-runs/{op_id}/cancel")
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"


def test_cannot_cancel_finalized_run(client):
    r = client.post(
        "/api/v1/agents/capital_monitoring_agent/run",
        json={"trigger": "weak-then-cancel"},
    )
    op_id = r.json()["operation_id"]
    # Run finalized as 'weak' (no proposed actions, no data) — not cancellable.
    r2 = client.post(f"/api/v1/agent-runs/{op_id}/cancel")
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# audit: every run emits operational events
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# proposed actions: human-in-command gate
# ---------------------------------------------------------------------------


def test_proposed_action_decide_lifecycle(client, db_session):
    """End-to-end approval gate: stage → list → decide → status = approved.
    Verifies humans remain in command and the agent never self-advances."""

    class MiniAgent(BaseAgent):
        name = "mini_decide_agent"
        version = "0.0.1"
        purpose = "test"
        allowed_actions = ("mini_test_action",)
        required_approvals = ("mini_test_action",)
        accessible_domains = ("test",)
        confidence_threshold = 0
        workflow_key = "mini.decide"

        def _pipeline(self):
            def stage(ctx: StageContext) -> StageResult:
                self.stage_action(
                    ctx,
                    action_type="mini_test_action",
                    target_entity_type=None,
                    target_entity_id=None,
                    payload={"x": 1},
                    requires_approval=True,
                )
                return StageResult(output_payload={}, confidence=100)

            return [stage]

    result = run_agent(db_session, MiniAgent(), trigger="t", actor="ops")
    op_id = result.operation.id

    # List endpoint surfaces the pending action.
    listing = client.get(
        "/api/v1/proposed-actions",
        params={"operation_id": op_id, "status": "pending"},
    )
    assert listing.status_code == 200, listing.text
    pending = listing.json()
    assert len(pending) == 1
    action_id = pending[0]["id"]
    assert pending[0]["status"] == "pending"
    assert pending[0]["requires_approval"] is True

    # Decide → approved.
    decide = client.post(
        f"/api/v1/proposed-actions/{action_id}/decide",
        json={"decision": "approved", "decided_by": "ops@asgard.local", "note": "looks good"},
    )
    assert decide.status_code == 200, decide.text
    body = decide.json()
    assert body["status"] == "approved"
    assert body["payload"]["_decision"]["by"] == "ops@asgard.local"

    # Cannot decide twice.
    again = client.post(
        f"/api/v1/proposed-actions/{action_id}/decide",
        json={"decision": "rejected", "decided_by": "ops"},
    )
    assert again.status_code == 409

    # Audit event was published.
    events = client.get(
        "/api/v1/events", params={"topic": "agents", "since": 0, "limit": 100}
    ).json()
    types = {e["event_type"] for e in events["items"]}
    assert "proposed_action.approved" in types


def test_proposed_action_decide_rejects_invalid_decision(client, db_session):
    class MiniAgent(BaseAgent):
        name = "mini_invalid_decide_agent"
        version = "0.0.1"
        purpose = "test"
        allowed_actions = ("ok",)
        required_approvals = ("ok",)
        accessible_domains = ("test",)
        confidence_threshold = 0
        workflow_key = "mini.invalid"

        def _pipeline(self):
            def stage(ctx: StageContext) -> StageResult:
                self.stage_action(
                    ctx,
                    action_type="ok",
                    target_entity_type=None,
                    target_entity_id=None,
                    payload={},
                )
                return StageResult(output_payload={}, confidence=100)

            return [stage]

    result = run_agent(db_session, MiniAgent(), trigger="t", actor="ops")
    actions = (
        db_session.query(ProposedAction)
        .filter(ProposedAction.autonomy_operation_id == result.operation.id)
        .all()
    )
    aid = actions[0].id

    bad = client.post(
        f"/api/v1/proposed-actions/{aid}/decide",
        json={"decision": "fluffy", "decided_by": "ops"},
    )
    assert bad.status_code == 400


def test_proposed_action_decide_404_for_unknown(client):
    r = client.post(
        "/api/v1/proposed-actions/9999999/decide",
        json={"decision": "approved", "decided_by": "ops"},
    )
    assert r.status_code == 404


def test_agent_run_emits_audit_events(client):
    r = client.post(
        "/api/v1/agents/capital_monitoring_agent/run",
        json={"trigger": "audit-check"},
    )
    assert r.status_code == 201

    events = client.get(
        "/api/v1/events", params={"topic": "agents", "since": 0, "limit": 50}
    )
    assert events.status_code == 200
    types = {e["event_type"] for e in events.json()["items"]}
    assert "agent.run_started" in types
    assert any(t.startswith("agent.run_") for t in types)
