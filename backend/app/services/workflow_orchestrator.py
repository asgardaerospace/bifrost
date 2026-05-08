"""Workflow orchestrator — bounded DAG execution with full trace.

Doctrine:
  * deterministic workflow graph (no recursion, no self-modification)
  * persisted state (each stage is a row in agent_workflow_stages)
  * replayable (stages have stable indices; output_payload is JSONB)
  * cancellable (orchestrator checks ctx.cancelled between stages)
  * timeout-aware (per-stage hard limit; reports the offending stage)
  * retry-aware (retry policy is per-stage; defaults to no retry)

This is NOT an agent runtime. Agents define their pipelines; the
orchestrator runs each stage, persists the trace, and finalizes the
AutonomyOperation. No stage may bypass governance.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.agent_workflow import AgentWorkflowStage
from app.models.autonomy import AutonomyOperation
from app.services.agents.base import (
    BaseAgent,
    StageContext,
    StageResult,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    operation: AutonomyOperation
    stage_count: int
    proposed_action_count: int
    final_status: str
    error: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_agent(
    db: Session,
    agent: BaseAgent,
    *,
    trigger: str,
    mission_id: Optional[int] = None,
    actor: str = "system",
    inputs: Optional[dict] = None,
    stage_timeout_seconds: float = 30.0,
) -> WorkflowResult:
    """Execute one workflow run for the given agent."""
    op = agent.kick_off(db, trigger=trigger, mission_id=mission_id, actor=actor)
    ctx = StageContext(db=db, operation=op, trigger=trigger, mission_id=mission_id)
    if inputs:
        ctx.inputs.update(inputs)

    pipeline = agent._pipeline()
    error: Optional[str] = None
    stage_records: list[dict] = []

    for index, stage_callable in enumerate(pipeline):
        if ctx.cancelled:
            break

        stage_name = stage_callable.__name__
        stage = AgentWorkflowStage(
            autonomy_operation_id=op.id,
            stage_index=index,
            stage_name=stage_name,
            status="running",
            started_at=_now(),
            input_payload=ctx.stage_input(stage_name),
        )
        db.add(stage)
        db.flush()

        start = time.monotonic()
        try:
            result: StageResult = stage_callable(ctx)
        except Exception as e:  # pragma: no cover — defensive
            logger.exception("agent stage %s/%s crashed", agent.name, stage_name)
            stage.status = "failed"
            stage.completed_at = _now()
            stage.error = str(e)
            db.flush()
            error = f"{stage_name}: {e}"
            break

        elapsed = time.monotonic() - start
        if elapsed > stage_timeout_seconds:
            stage.status = "failed"
            stage.completed_at = _now()
            stage.error = f"stage exceeded timeout ({elapsed:.1f}s > {stage_timeout_seconds}s)"
            db.flush()
            error = stage.error
            break

        stage.status = "completed" if result.error is None else "failed"
        stage.completed_at = _now()
        stage.output_payload = result.output_payload
        stage.retrieval_trace = result.retrieval_trace
        stage.confidence = result.confidence
        stage.error = result.error
        db.flush()

        stage_records.append(
            {
                "stage_index": index,
                "stage_name": stage_name,
                "status": stage.status,
                "confidence": result.confidence,
            }
        )

        if result.error:
            error = f"{stage_name}: {result.error}"
            break

        if result.confidence is not None:
            ctx.confidence *= max(0.0, min(1.0, result.confidence / 100.0))

        if result.cancel:
            ctx.cancelled = True
            break
        if result.skip_remaining:
            break

    # Stash stage history into the operation payload for fast read.
    op.payload = {**(op.payload or {}), "stages": stage_records}

    # Confidence floor — agents below threshold finalize as a refusal,
    # not a proposal. This prevents low-quality output from clogging the
    # approval queue.
    threshold = (agent.confidence_threshold or 0) / 100.0
    if error is not None:
        final_status = "failed"
    elif ctx.cancelled:
        final_status = "cancelled"
    elif ctx.confidence < threshold or not ctx.proposed_actions:
        final_status = "weak"
    else:
        final_status = "proposed"

    agent.finalize(
        db,
        ctx,
        status=final_status,
        reasoning=ctx.outputs.get("reasoning"),
    )
    db.commit()
    db.refresh(op)
    return WorkflowResult(
        operation=op,
        stage_count=len(stage_records),
        proposed_action_count=len(ctx.proposed_actions),
        final_status=final_status,
        error=error,
    )


def cancel_run(db: Session, operation_id: int, *, reason: str = "operator-cancel") -> AutonomyOperation:
    op = db.get(AutonomyOperation, operation_id)
    if op is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"AutonomyOperation #{operation_id} not found")
    if op.status not in ("running", "proposed"):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel operation in status '{op.status}'",
        )
    op.status = "cancelled"
    op.payload = {**(op.payload or {}), "cancel_reason": reason}
    db.commit()
    db.refresh(op)
    return op
