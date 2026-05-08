"""QueueCoordinationAgent — proposes queue reprioritization for overdue items.

Bounded scope:
  - reads:    execution_queue_items
  - proposes: stage_queue_reprioritize
  - approves: human required
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.models.execution_queue import ExecutionQueueItem
from app.services.agents import register
from app.services.agents.base import (
    BaseAgent,
    StageContext,
    StageResult,
)


class QueueCoordinationAgent(BaseAgent):
    name = "queue_coordination_agent"
    version = "0.1.0"
    purpose = (
        "Detects overdue queue items at low priority and stages "
        "reprioritization proposals. Mutations are gated by approval."
    )
    allowed_actions = ("stage_queue_reprioritize",)
    required_approvals = ("stage_queue_reprioritize",)
    accessible_domains = ("execution_queue_item",)
    confidence_threshold = 60
    workflow_key = "queue.coordinate"

    def _pipeline(self):
        return [scan_overdue, propose_reprioritize]


def scan_overdue(ctx: StageContext) -> StageResult:
    db = ctx.db
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(ExecutionQueueItem)
        .where(ExecutionQueueItem.status == "queued")
        .where(ExecutionQueueItem.due_at.is_not(None))
        .where(ExecutionQueueItem.due_at < now)
        .where(ExecutionQueueItem.priority_score < 60)
        .where(ExecutionQueueItem.deleted_at.is_(None))
    ).all()
    ctx.outputs["overdue_ids"] = [r.id for r in rows]
    return StageResult(
        output_payload={"overdue_low_priority": len(rows)},
        confidence=80 if rows else 25,
    )


def propose_reprioritize(ctx: StageContext) -> StageResult:
    db = ctx.db
    ids = ctx.outputs.get("overdue_ids", [])
    if not ids:
        return StageResult(output_payload={"proposed": 0}, confidence=25)
    rows = db.scalars(
        select(ExecutionQueueItem).where(ExecutionQueueItem.id.in_(ids))
    ).all()
    from app.services.agents import get as get_agent

    ag = get_agent(ctx.operation.agent_name)
    if ag is None:
        return StageResult(output_payload={}, confidence=0)

    proposed = 0
    for row in rows:
        ag.stage_action(
            ctx,
            action_type="stage_queue_reprioritize",
            target_entity_type="execution_queue_item",
            target_entity_id=row.id,
            payload={
                "current_priority": row.priority_score,
                "suggested_priority": 80,
                "title": row.title,
                "due_at": row.due_at.isoformat() if row.due_at else None,
                "rationale": (
                    f"Queue item '{row.title}' is overdue at priority "
                    f"{row.priority_score}; recommend reprioritizing to ≥80."
                ),
            },
            requires_approval=True,
        )
        proposed += 1
    ctx.outputs["proposed"] = proposed
    ctx.outputs["reasoning"] = (
        f"Staged {proposed} reprioritization proposal(s). No queue items "
        "were modified; all changes require operator approval."
    )
    return StageResult(
        output_payload={"proposed": proposed},
        confidence=80 if proposed else 25,
    )


register(QueueCoordinationAgent())
