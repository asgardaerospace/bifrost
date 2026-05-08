"""Base agent + workflow stage primitives.

Sprint 6 contract:
  * Agents declare metadata as class attributes (purpose, allowed_actions,
    required_approvals, accessible_domains, confidence_threshold).
  * Each agent implements `_pipeline()` returning an ordered list of stage
    callables. The base class runs them, persists trace rows, and stages
    proposed_actions for human approval.
  * Agents NEVER mutate operational state directly. Their only output is
    `ProposedAction` rows (audit-traceable, approval-gated) and synthesis
    summaries persisted as memory + operational events.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.models.agent_workflow import AgentWorkflowStage
from app.models.autonomy import AutonomyOperation, ProposedAction
from app.schemas.operational_event import OperationalEventCreate
from app.services import events as events_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# stage shapes
# ---------------------------------------------------------------------------


@dataclass
class StageContext:
    """State threaded through a workflow's stages.

    Stages mutate this object; the orchestrator persists snapshots after
    each stage so an operator can replay the run.
    """

    db: Session
    operation: AutonomyOperation
    trigger: str
    mission_id: Optional[int] = None
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    proposed_actions: list[ProposedAction] = field(default_factory=list)
    cancelled: bool = False
    confidence: float = 1.0  # cumulative product across stages

    def stage_input(self, stage_name: str) -> dict[str, Any]:
        return {
            "trigger": self.trigger,
            "mission_id": self.mission_id,
            "inherited": dict(self.inputs),
            "stage_name": stage_name,
        }


@dataclass
class StageResult:
    """What a stage emits to be persisted on its workflow_stage row."""

    output_payload: dict[str, Any] = field(default_factory=dict)
    retrieval_trace: Optional[dict[str, Any]] = None
    confidence: Optional[int] = None  # 0..100; multiplied into ctx.confidence
    error: Optional[str] = None
    cancel: bool = False
    skip_remaining: bool = False


# A stage is a callable: (ctx) -> StageResult
StageCallable = Callable[[StageContext], StageResult]


# ---------------------------------------------------------------------------
# descriptor (for the /agents read-side API)
# ---------------------------------------------------------------------------


@dataclass
class AgentDescriptor:
    name: str
    version: str
    purpose: str
    allowed_actions: list[str]
    required_approvals: list[str]
    accessible_domains: list[str]
    confidence_threshold: int
    workflow_key: str
    stages: list[str]
    escalation_rules: list[str]


# ---------------------------------------------------------------------------
# base agent
# ---------------------------------------------------------------------------


class BaseAgent:
    name: str = "abstract"
    version: str = "0.1.0"
    purpose: str = ""
    allowed_actions: tuple[str, ...] = ()
    required_approvals: tuple[str, ...] = ()  # actions requiring approval
    accessible_domains: tuple[str, ...] = ()
    confidence_threshold: int = 50  # 0..100
    workflow_key: str = "default"
    escalation_rules: tuple[str, ...] = (
        "any proposed action requires human approval before execution",
    )

    def descriptor(self) -> AgentDescriptor:
        return AgentDescriptor(
            name=self.name,
            version=self.version,
            purpose=self.purpose,
            allowed_actions=list(self.allowed_actions),
            required_approvals=list(self.required_approvals),
            accessible_domains=list(self.accessible_domains),
            confidence_threshold=self.confidence_threshold,
            workflow_key=self.workflow_key,
            stages=[s.__name__ for s in self._pipeline()],
            escalation_rules=list(self.escalation_rules),
        )

    # Subclasses override.
    def _pipeline(self) -> list[StageCallable]:
        return []

    # ---------- helpers for subclasses ----------

    def stage_action(
        self,
        ctx: StageContext,
        *,
        action_type: str,
        target_entity_type: Optional[str],
        target_entity_id: Optional[int],
        payload: dict[str, Any],
        requires_approval: bool = True,
    ) -> ProposedAction:
        """Stage a proposed action. Always governance-gated by default."""
        if action_type not in self.allowed_actions:
            raise PermissionError(
                f"agent '{self.name}' is not permitted to propose action '{action_type}'"
            )
        rqa = requires_approval or action_type in self.required_approvals
        action = ProposedAction(
            autonomy_operation_id=ctx.operation.id,
            action_type=action_type,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            payload=payload,
            status="pending",
            requires_approval=rqa,
        )
        ctx.db.add(action)
        ctx.db.flush()
        ctx.proposed_actions.append(action)
        return action

    # ---------- run lifecycle (called by orchestrator) ----------

    def kick_off(
        self,
        db: Session,
        *,
        trigger: str,
        mission_id: Optional[int] = None,
        actor: str = "system",
    ) -> AutonomyOperation:
        """Persist the AutonomyOperation row that frames this run."""
        op = AutonomyOperation(
            agent_name=self.name,
            operation_type=self.workflow_key,
            mission_id=mission_id,
            status="running",
            confidence_score=0,
            reasoning="",
            payload={"trigger": trigger, "actor": actor},
            trigger=trigger,
            workflow_key=self.workflow_key,
        )
        db.add(op)
        db.flush()
        events_service.publish(
            db,
            OperationalEventCreate(
                topic="agents",
                event_type="agent.run_started",
                mission_id=mission_id,
                entity_type="autonomy_operation",
                entity_id=op.id,
                actor=self.name,
                payload={"trigger": trigger, "workflow_key": self.workflow_key},
            ),
        )
        return op

    def finalize(
        self,
        db: Session,
        ctx: StageContext,
        *,
        status: str = "proposed",
        reasoning: Optional[str] = None,
    ) -> AutonomyOperation:
        op = ctx.operation
        op.status = status
        op.confidence_score = int(round(min(1.0, max(0.0, ctx.confidence)) * 100))
        if reasoning is not None:
            op.reasoning = reasoning
        op.payload = {**(op.payload or {}), "outputs": ctx.outputs}
        db.flush()
        events_service.publish(
            db,
            OperationalEventCreate(
                topic="agents",
                event_type=f"agent.run_{status}",
                mission_id=ctx.mission_id,
                entity_type="autonomy_operation",
                entity_id=op.id,
                actor=self.name,
                severity="notice" if status == "proposed" else "info",
                payload={
                    "proposed_actions": len(ctx.proposed_actions),
                    "confidence": op.confidence_score,
                    "stages_completed": len([s for s in op.payload.get("stages", [])]),
                },
            ),
        )
        return op


def _now() -> datetime:
    return datetime.now(timezone.utc)
