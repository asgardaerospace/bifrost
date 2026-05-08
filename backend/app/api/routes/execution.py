"""Execution Queue HTTP routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.schemas.approval import ApprovalRead
from app.schemas.execution import (
    ExecutionQueue,
    ExecutionQueueItemCreate,
    ExecutionQueueItemRead,
    ExecutionQueueItemUpdate,
)
from app.services import execution as execution_service
from app.services import governance as governance_service

router = APIRouter()


@router.get("/execution/queue", response_model=ExecutionQueue)
def queue(
    mission_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    item_type: Optional[list[str]] = Query(None),
    domain: Optional[list[str]] = Query(
        None,
        description=(
            "Filter by source domain (e.g. investor_opportunity, market_opportunity, "
            "task, communication). Repeat to allow multiple."
        ),
    ),
    min_priority: Optional[int] = Query(None, ge=0, le=100),
    requires_approval: Optional[bool] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> ExecutionQueue:
    return execution_service.build_queue(
        db,
        mission_id=mission_id,
        status=status_filter,
        item_types=item_type,
        domains=domain,
        min_priority=min_priority,
        requires_approval=requires_approval,
        limit=limit,
    )


@router.get("/execution/blockers", response_model=ExecutionQueue)
def blockers(
    mission_id: Optional[int] = Query(None), db: Session = Depends(get_db)
) -> ExecutionQueue:
    return execution_service.list_blockers(db, mission_id=mission_id)


@router.get("/execution/approvals", response_model=ExecutionQueue)
def pending_approvals(
    mission_id: Optional[int] = Query(None), db: Session = Depends(get_db)
) -> ExecutionQueue:
    return execution_service.list_pending_approvals(db, mission_id=mission_id)


def _row_to_response(row) -> ExecutionQueueItemRead:
    return ExecutionQueueItemRead(
        id=row.id,
        item_type=row.item_type,
        source_type=row.source_type,
        source_id=row.source_id,
        mission_id=row.mission_id,
        title=row.title,
        summary=row.summary,
        status=row.status,
        priority_score=row.priority_score,
        pressure_score=row.pressure_score,
        owner=row.owner,
        due_at=row.due_at,
        completed_at=row.completed_at,
        blocked_reason=row.blocked_reason,
        created_at=row.created_at,
        is_projected=False,
        requires_approval=row.requires_approval,
        meta=row.meta,
    )


@router.post(
    "/execution/actions",
    response_model=ExecutionQueueItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_action(
    payload: ExecutionQueueItemCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ExecutionQueueItemRead:
    row = execution_service.create_item(
        db,
        payload,
        actor=user.email,
        requires_approval=payload.requires_approval,
    )
    return _row_to_response(row)


@router.patch(
    "/execution/actions/{item_id}", response_model=ExecutionQueueItemRead
)
def update_action(
    item_id: int,
    payload: ExecutionQueueItemUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ExecutionQueueItemRead:
    row = execution_service.update_item(db, item_id, payload, actor=user.email)
    return _row_to_response(row)


@router.post(
    "/execution/actions/{item_id}/request-approval",
    response_model=ApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
def request_action_approval(
    item_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ApprovalRead:
    approval = execution_service.request_approval(db, item_id, actor=user.email)
    return ApprovalRead.model_validate(approval)


@router.post(
    "/execution/actions/{item_id}/decide",
    response_model=ApprovalRead,
)
def decide_action_approval(
    item_id: int,
    decision: str = Query(..., pattern="^(approved|rejected)$"),
    note: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ApprovalRead:
    """Approve or reject the latest pending Approval for this queue item."""
    approval = governance_service.find_approval_for(
        db,
        entity_type=governance_service.ENTITY_QUEUE_ITEM,
        entity_id=item_id,
    )
    if approval is None:
        raise HTTPException(
            status_code=404, detail="no approval row for this queue item"
        )
    decided = governance_service.decide(
        db,
        approval.id,
        decision=decision,
        reviewer=user.email,
        note=note,
    )
    return ApprovalRead.model_validate(decided)
