# Bifrost — Workflow Governance

> Governance-first autonomy: every proposal attributable, every workflow
> traceable, every approval auditable.

## Components

| Layer | File | Purpose |
|---|---|---|
| Approval ledger | `services/governance.py` | Polymorphic approvals on queue items + proposed actions. |
| Autonomy operations | `models/autonomy.py` | Per-run record of agent operations + proposed actions. |
| Execution policies | `services/policy.py` | Hard ceilings: confidence floors, rate limits, approval-required. |
| Audit trail | `services/audit.py` | Append-only record on `audit` topic. |
| Workflow stages | `models/agent_workflow.py` | Per-stage timing & status for a workflow run. |

## Policy registry

`EXECUTION_POLICIES` lives in `services/policy.py`. Each entry declares:

```python
ExecutionPolicy(
    action_type="agent_recommend_action",
    requires_approval=True,         # routes through Approval ledger
    min_confidence=0.45,            # deny below this
    max_per_mission_per_hour=20,    # rate ceiling per mission
    escalation_role="executive",    # who owns escalation
    description="...",
)
```

Built-in policies:
* `queue_item_complete` — approval-required.
* `agent_recommend_action` — approval-required, min confidence 0.45,
  20/hr/mission.
* `agent_autonomous_observe` — read-only, no approval.
* `agent_autonomous_synthesize` — synthesis output, min confidence 0.4.
* `communication_send` — approval-required, min confidence 0.6, executive
  escalation.
* `policy_override` — approval-required, admin escalation.

Global ceilings (via env): `GOVERNANCE_AUTONOMY_CONFIDENCE_FLOOR`,
`GOVERNANCE_MAX_PROPOSALS_PER_MISSION_PER_HOUR`. The effective floor is
`max(policy.min_confidence, global_floor)`.

## Decision flow

```python
decision = policy.evaluate(
    db,
    action_type="agent_recommend_action",
    confidence=0.62,
    mission_id=12,
    actor="capital_monitoring_agent",
)
if not decision.allow:
    # deny is recorded as audit + governance event; caller escalates.
    return
```

Every call emits:
* a `governance.policy.allow` or `governance.policy.deny` operational event
  (visible in the realtime ribbon and `/events?topic=governance`);
* an audit row on the `audit` topic with the full payload;
* `policy.allow.<action>` or `policy.deny.<action>` counter for /metrics.

## Override

```http
POST /api/v1/governance/policies/{action_type}/override
{ "reason": "manual override — investor briefing under deadline", "mission_id": 12 }
```

Requires `policy.override` permission (admin/executive). The override itself
is audited as `audit.policy.override` — operators trade convenience for
visibility, never silence.

## Audit retrieval

```http
GET /api/v1/governance/audit?limit=50&action=approval.decide&mission_id=12
```

Backed by `OperationalEvent` rows on topic=audit; supports filter by action
verb and mission. Read-only, append-only — no edit/delete from this layer.

## Workflow trace continuity

Every operational event publish copies the active trace metadata into
`payload._trace`:

```json
{
  "request_id": "...",
  "trace_id": "...",
  "workflow_id": "...",   # set by agent runtime
  "actor": "..."
}
```

A failure can be followed end-to-end: HTTP request → service span → event
publish → ws fanout → next workflow stage.
