"""Agent registry + workflow trace HTTP routes (Sprint 6)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.agent_workflow import AgentWorkflowStage
from app.models.autonomy import AutonomyOperation, ProposedAction
from app.schemas.agent import (
    AgentDescriptorRead,
    AgentRunReport,
    AgentRunRequest,
    AgentWorkflowStageRead,
    AutonomyOperationRead,
    ProposedActionDecisionRequest,
    ProposedActionRead,
    WorkflowTraceRead,
)
from app.schemas.operational_event import OperationalEventCreate
from app.services import agent_coordination, events as events_service
from app.services.agents import descriptors as agent_descriptors
from app.services.agents import get as get_agent
from app.services.workflow_orchestrator import cancel_run, run_agent

router = APIRouter()


@router.get("/agents", response_model=list[AgentDescriptorRead])
def list_agents() -> list[AgentDescriptorRead]:
    return [AgentDescriptorRead(**vars(d)) for d in agent_descriptors()]


@router.get("/agents/{name}", response_model=AgentDescriptorRead)
def get_agent_descriptor(name: str) -> AgentDescriptorRead:
    agent = get_agent(name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not registered")
    return AgentDescriptorRead(**vars(agent.descriptor()))


@router.post(
    "/agents/{name}/run",
    response_model=AgentRunReport,
    status_code=status.HTTP_201_CREATED,
)
def run_named_agent(
    name: str,
    payload: AgentRunRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AgentRunReport:
    agent = get_agent(name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not registered")
    result = run_agent(
        db,
        agent,
        trigger=payload.trigger,
        mission_id=payload.mission_id,
        actor=user.email,
    )
    handoff_op_ids: list[int] = []
    if payload.propagate_handoffs and result.final_status == "proposed":
        for h in agent_coordination.fire_handoffs(db, name, result):
            handoff_op_ids.append(h.operation.id)
    return AgentRunReport(
        operation_id=result.operation.id,
        agent_name=name,
        workflow_key=agent.workflow_key,
        final_status=result.final_status,
        confidence=result.operation.confidence_score,
        stage_count=result.stage_count,
        proposed_action_count=result.proposed_action_count,
        error=result.error,
        handoff_runs=handoff_op_ids,
    )


@router.post(
    "/agent-runs/{operation_id}/cancel",
    response_model=AutonomyOperationRead,
)
def cancel_agent_run(
    operation_id: int, db: Session = Depends(get_db)
) -> AutonomyOperationRead:
    op = cancel_run(db, operation_id)
    return AutonomyOperationRead.model_validate(op)


@router.get(
    "/agent-runs", response_model=list[AutonomyOperationRead]
)
def list_agent_runs(
    agent_name: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    mission_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AutonomyOperationRead]:
    stmt = select(AutonomyOperation)
    if agent_name:
        stmt = stmt.where(AutonomyOperation.agent_name == agent_name)
    if status_filter:
        stmt = stmt.where(AutonomyOperation.status == status_filter)
    if mission_id is not None:
        stmt = stmt.where(AutonomyOperation.mission_id == mission_id)
    stmt = stmt.order_by(AutonomyOperation.proposed_at.desc()).limit(limit)
    rows = list(db.scalars(stmt).all())
    return [AutonomyOperationRead.model_validate(r) for r in rows]


@router.get(
    "/agent-runs/{operation_id}", response_model=WorkflowTraceRead
)
def get_workflow_trace(
    operation_id: int, db: Session = Depends(get_db)
) -> WorkflowTraceRead:
    op = db.get(AutonomyOperation, operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"AutonomyOperation #{operation_id} not found")
    stages = list(
        db.scalars(
            select(AgentWorkflowStage)
            .where(AgentWorkflowStage.autonomy_operation_id == operation_id)
            .order_by(AgentWorkflowStage.stage_index.asc())
        ).all()
    )
    proposed_count = (
        db.scalar(
            select(__import__("sqlalchemy").func.count(ProposedAction.id)).where(
                ProposedAction.autonomy_operation_id == operation_id
            )
        )
        or 0
    )
    return WorkflowTraceRead(
        operation=AutonomyOperationRead.model_validate(op),
        stages=[AgentWorkflowStageRead.model_validate(s) for s in stages],
        proposed_action_count=int(proposed_count),
    )


# ---------------------------------------------------------------------------
# Proposed actions — read + decide (human-in-command gate)
# ---------------------------------------------------------------------------


@router.get(
    "/proposed-actions", response_model=list[ProposedActionRead]
)
def list_proposed_actions(
    status_filter: Optional[str] = Query(None, alias="status"),
    operation_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ProposedActionRead]:
    stmt = select(ProposedAction)
    if status_filter:
        stmt = stmt.where(ProposedAction.status == status_filter)
    if operation_id is not None:
        stmt = stmt.where(ProposedAction.autonomy_operation_id == operation_id)
    stmt = stmt.order_by(ProposedAction.created_at.desc()).limit(limit)
    rows = list(db.scalars(stmt).all())
    return [ProposedActionRead.model_validate(r) for r in rows]


@router.post(
    "/proposed-actions/{action_id}/decide",
    response_model=ProposedActionRead,
)
def decide_proposed_action(
    action_id: int,
    payload: ProposedActionDecisionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ProposedActionRead:
    """Human-in-command gate: only operators decide whether a proposed
    action becomes approved or rejected. The agent itself NEVER advances
    a ProposedAction past `pending` on its own."""
    action = db.get(ProposedAction, action_id)
    if action is None:
        raise HTTPException(
            status_code=404, detail=f"ProposedAction #{action_id} not found"
        )
    decision = (payload.decision or "").lower()
    if decision not in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="decision must be one of: approved, rejected",
        )
    if action.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"ProposedAction #{action_id} already {action.status}",
        )

    action.status = decision
    actor = payload.decided_by or user.email
    pl = dict(action.payload or {})
    pl["_decision"] = {"by": actor, "decision": decision, "note": payload.note}
    action.payload = pl
    db.flush()

    events_service.publish(
        db,
        OperationalEventCreate(
            topic="agents",
            event_type=f"proposed_action.{decision}",
            entity_type="proposed_action",
            entity_id=action.id,
            actor=actor,
            severity="notice",
            payload={
                "autonomy_operation_id": action.autonomy_operation_id,
                "action_type": action.action_type,
                "note": payload.note,
            },
        ),
    )
    db.commit()
    db.refresh(action)
    return ProposedActionRead.model_validate(action)
