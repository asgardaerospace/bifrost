from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from fastapi import HTTPException, status as http_status

from app.core.database import get_db
from app.integrations.investor_engine import writes_service as engine_writes_service
from app.models.approval import Approval
from app.models.communication import Communication
from app.schemas.approval import ApprovalDecisionInput, ApprovalRead
from app.services import approvals as approvals_service
from app.services import communications as comm_service

router = APIRouter()


@router.get("/", response_model=list[ApprovalRead])
def list_approvals(
    status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ApprovalRead]:
    stmt = select(Approval)
    if status is not None:
        stmt = stmt.where(Approval.status == status)
    stmt = stmt.order_by(desc(Approval.created_at)).offset(skip).limit(limit)
    approvals = list(db.scalars(stmt).all())

    # Pull communication context in one batch (drafts targeting comms
    # are the common case — we want subject + source badge).
    comm_ids = [
        a.entity_id for a in approvals if a.entity_type == "communication"
    ]
    comm_by_id: dict[int, Communication] = {}
    if comm_ids:
        comms = db.scalars(
            select(Communication).where(Communication.id.in_(comm_ids))
        ).all()
        comm_by_id = {c.id: c for c in comms}

    results: list[ApprovalRead] = []
    for a in approvals:
        read = ApprovalRead.model_validate(a)
        if a.entity_type == "communication":
            c = comm_by_id.get(a.entity_id)
            if c is not None:
                read = read.model_copy(
                    update={
                        "communication_subject": c.subject,
                        "communication_status": c.status,
                        "source_system": c.source_system,
                        "source_external_id": c.source_external_id,
                    }
                )
        results.append(read)
    return results


def _load_pending_approval(db: Session, approval_id: int) -> Approval:
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != comm_service.APPROVAL_PENDING:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Approval is not pending (current: '{approval.status}')",
        )
    return approval


@router.post("/{approval_id}/approve", response_model=ApprovalRead)
def approve(
    approval_id: int,
    payload: ApprovalDecisionInput,
    db: Session = Depends(get_db),
) -> ApprovalRead:
    approval = _load_pending_approval(db, approval_id)

    if approval.action == engine_writes_service.ACTION_ENGINE_WRITE:
        engine_writes_service.approve_engine_write(
            db,
            approval,
            reviewer=payload.reviewer,
            decision_note=payload.decision_note,
        )
        db.refresh(approval)
        return approval

    return approvals_service.approve_send(
        db,
        approval_id,
        reviewer=payload.reviewer,
        decision_note=payload.decision_note,
    )


@router.post("/{approval_id}/reject", response_model=ApprovalRead)
def reject(
    approval_id: int,
    payload: ApprovalDecisionInput,
    db: Session = Depends(get_db),
) -> ApprovalRead:
    approval = _load_pending_approval(db, approval_id)

    if approval.action == engine_writes_service.ACTION_ENGINE_WRITE:
        return engine_writes_service.reject_engine_write(
            db,
            approval,
            reviewer=payload.reviewer,
            decision_note=payload.decision_note,
        )

    return approvals_service.reject_send(
        db,
        approval_id,
        reviewer=payload.reviewer,
        decision_note=payload.decision_note,
    )
