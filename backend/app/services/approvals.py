"""Approval decision handling for send-communication approvals.

Transitions:
    Approval:  pending -> approved | rejected
    Communication (on approved + successful send):  pending_approval -> sent
    Communication (on rejected):                    pending_approval -> draft
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.communication import Communication
from app.models.workflow import WorkflowRun
from app.services import communications as comm_service
from app.services import email as email_service
from app.services.activity import log_activity


def _load_pending(db: Session, approval_id: int) -> Approval:
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != comm_service.APPROVAL_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval is not pending (current: '{approval.status}')",
        )
    return approval


def _load_workflow_run(db: Session, approval: Approval) -> Optional[WorkflowRun]:
    if approval.workflow_run_id is None:
        return None
    return db.get(WorkflowRun, approval.workflow_run_id)


def approve_send(
    db: Session,
    approval_id: int,
    *,
    reviewer: str,
    decision_note: Optional[str] = None,
) -> Approval:
    approval = _load_pending(db, approval_id)
    if approval.action != comm_service.ACTION_SEND_COMMUNICATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported approval action: '{approval.action}'",
        )
    if approval.entity_type != comm_service.ENTITY_COMMUNICATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval is not attached to a communication",
        )

    comm = db.get(Communication, approval.entity_id)
    if comm is None or comm.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Communication not found")
    if comm.status != comm_service.STATUS_PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Communication not in pending_approval (current: '{comm.status}')",
        )

    now = datetime.now(timezone.utc)
    approval.status = comm_service.APPROVAL_APPROVED
    approval.reviewer = reviewer
    approval.reviewed_at = now
    if decision_note is not None:
        approval.decision_note = decision_note
    db.flush()

    run = _load_workflow_run(db, approval)
    if run is not None:
        run.status = "in_progress"
    db.flush()

    # Call send boundary. On failure we keep the communication in
    # pending_approval (so it can be retried) and mark the workflow_run
    # failed. The approval itself stays approved; auditable.
    result = email_service.send_communication(comm)

    if not result.success:
        if run is not None:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = result.error or "send failed"
        log_activity(
            db,
            entity_type=comm_service.ENTITY_COMMUNICATION,
            entity_id=comm.id,
            event_type="communication.send_failed",
            summary=f"Send failed for communication #{comm.id}",
            actor=reviewer,
            details={
                "approval_id": approval.id,
                "provider": result.provider,
                "error": result.error,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email provider failed: {result.error}",
        )

    comm.status = comm_service.STATUS_SENT
    comm.sent_at = result.sent_at
    db.flush()

    if run is not None:
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.result_payload = {
            "communication_id": comm.id,
            "provider": result.provider,
            "message_id": result.message_id,
            "sent_at": result.sent_at.isoformat(),
        }

    log_activity(
        db,
        entity_type=comm_service.ENTITY_COMMUNICATION,
        entity_id=comm.id,
        event_type="communication.approved_and_sent",
        summary=f"Communication #{comm.id} approved by {reviewer} and sent via {result.provider}",
        actor=reviewer,
        details={
            "approval_id": approval.id,
            "provider": result.provider,
            "message_id": result.message_id,
        },
    )

    db.commit()
    db.refresh(approval)
    return approval


def reject_send(
    db: Session,
    approval_id: int,
    *,
    reviewer: str,
    decision_note: Optional[str] = None,
) -> Approval:
    approval = _load_pending(db, approval_id)

    now = datetime.now(timezone.utc)
    approval.status = comm_service.APPROVAL_REJECTED
    approval.reviewer = reviewer
    approval.reviewed_at = now
    if decision_note is not None:
        approval.decision_note = decision_note
    db.flush()

    run = _load_workflow_run(db, approval)
    if run is not None:
        run.status = "completed"
        run.completed_at = now
        run.result_payload = {"decision": "rejected", "reviewer": reviewer}
    db.flush()

    comm: Optional[Communication] = None
    if approval.entity_type == comm_service.ENTITY_COMMUNICATION:
        comm = db.get(Communication, approval.entity_id)
        if comm is not None and comm.status == comm_service.STATUS_PENDING_APPROVAL:
            comm.status = comm_service.STATUS_DRAFT
            db.flush()

    log_activity(
        db,
        entity_type=approval.entity_type,
        entity_id=approval.entity_id,
        event_type="approval.rejected",
        summary=(
            f"Approval #{approval.id} rejected by {reviewer}"
            + (f" — {decision_note}" if decision_note else "")
        ),
        actor=reviewer,
        details={"approval_id": approval.id, "action": approval.action},
    )

    db.commit()
    db.refresh(approval)
    return approval
