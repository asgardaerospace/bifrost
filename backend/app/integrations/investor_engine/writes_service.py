"""Request + approval flow for investor engine writes.

Writes against the investor engine are approval-gated. A user proposes
a write, which creates:

    - an Approval row (status=pending, action=ACTION_ENGINE_WRITE)
    - a WorkflowRun (for audit)

No pending_engine_writes row exists yet. On approval, we enqueue the
row via `writer.enqueue_write`. On rejection, nothing is enqueued.

This keeps the "approval is the gate" invariant: the outbox is only
populated after an approved decision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.integrations.investor_engine import writer
from app.integrations.investor_engine.writes_models import (
    PendingEngineWrite,
    SUPPORTED_ACTIONS,
)
from app.models.approval import Approval
from app.models.workflow import WorkflowRun
from app.services import communications as comm_service
from app.services.activity import log_activity

ENTITY_ENGINE_WRITE_REQUEST = "engine_write_request"
ACTION_ENGINE_WRITE = "engine_write"
WORKFLOW_ENGINE_WRITE = "investor_engine.write"


def request_engine_write_approval(
    db: Session,
    *,
    external_id: str,
    action_type: str,
    payload: dict[str, Any],
    requested_by: Optional[str] = None,
    note: Optional[str] = None,
) -> Approval:
    """Create the approval + workflow run for a proposed engine write."""
    if action_type not in SUPPORTED_ACTIONS:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported action_type: {action_type!r}",
        )

    now = datetime.now(timezone.utc)
    run = WorkflowRun(
        workflow_key=WORKFLOW_ENGINE_WRITE,
        entity_type=ENTITY_ENGINE_WRITE_REQUEST,
        entity_id=0,  # patched below
        status="pending_approval",
        triggered_by=requested_by,
        started_at=now,
        input_payload={
            "external_id": external_id,
            "action_type": action_type,
            "payload": payload,
        },
    )
    db.add(run)
    db.flush()
    run.entity_id = run.id  # self-reference; approval links via workflow_run_id
    db.flush()

    approval = Approval(
        entity_type=ENTITY_ENGINE_WRITE_REQUEST,
        entity_id=run.id,
        workflow_run_id=run.id,
        action=ACTION_ENGINE_WRITE,
        status=comm_service.APPROVAL_PENDING,
        requested_by=requested_by,
        decision_note=note,
    )
    db.add(approval)
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_ENGINE_WRITE_REQUEST,
        entity_id=run.id,
        event_type="engine_write.requested",
        summary=(
            f"Engine write '{action_type}' requested for {external_id}"
        ),
        actor=requested_by,
        details={
            "external_id": external_id,
            "action_type": action_type,
            "approval_id": approval.id,
            "workflow_run_id": run.id,
        },
    )

    db.commit()
    db.refresh(approval)
    return approval


def approve_engine_write(
    db: Session,
    approval: Approval,
    *,
    reviewer: str,
    decision_note: Optional[str] = None,
) -> PendingEngineWrite:
    """Mark approval approved and enqueue the pending_engine_writes row.

    Caller must have already validated that `approval` is pending and
    of action == ACTION_ENGINE_WRITE.
    """
    run = (
        db.get(WorkflowRun, approval.workflow_run_id)
        if approval.workflow_run_id
        else None
    )
    if run is None or not run.input_payload:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Engine write approval is missing its workflow run payload",
        )

    inp = run.input_payload
    external_id = inp.get("external_id")
    action_type = inp.get("action_type")
    payload = inp.get("payload") or {}
    if not external_id or not action_type:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Workflow run payload is incomplete",
        )

    now = datetime.now(timezone.utc)
    approval.status = comm_service.APPROVAL_APPROVED
    approval.reviewer = reviewer
    approval.reviewed_at = now
    if decision_note is not None:
        approval.decision_note = decision_note
    db.flush()

    try:
        row = writer.enqueue_write(
            db,
            external_id=external_id,
            action_type=action_type,
            payload=payload,
            approval_id=approval.id,
            requested_by=approval.requested_by,
        )
    except writer.WriterError as exc:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = str(exc)
        db.commit()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Failed to enqueue write: {exc}",
        )

    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    run.result_payload = {"pending_engine_write_id": row.id}

    log_activity(
        db,
        entity_type=ENTITY_ENGINE_WRITE_REQUEST,
        entity_id=run.id,
        event_type="engine_write.enqueued_after_approval",
        summary=(
            f"Engine write #{row.id} enqueued after approval by {reviewer}"
        ),
        actor=reviewer,
        details={
            "approval_id": approval.id,
            "pending_engine_write_id": row.id,
            "external_id": external_id,
            "action_type": action_type,
        },
    )
    db.commit()
    db.refresh(row)
    return row


def reject_engine_write(
    db: Session,
    approval: Approval,
    *,
    reviewer: str,
    decision_note: Optional[str] = None,
) -> Approval:
    now = datetime.now(timezone.utc)
    approval.status = comm_service.APPROVAL_REJECTED
    approval.reviewer = reviewer
    approval.reviewed_at = now
    if decision_note is not None:
        approval.decision_note = decision_note
    db.flush()

    run = (
        db.get(WorkflowRun, approval.workflow_run_id)
        if approval.workflow_run_id
        else None
    )
    if run is not None:
        run.status = "completed"
        run.completed_at = now
        run.result_payload = {"decision": "rejected", "reviewer": reviewer}

    log_activity(
        db,
        entity_type=ENTITY_ENGINE_WRITE_REQUEST,
        entity_id=approval.entity_id,
        event_type="engine_write.rejected",
        summary=f"Engine write approval #{approval.id} rejected by {reviewer}",
        actor=reviewer,
        details={
            "approval_id": approval.id,
            "decision_note": decision_note,
        },
    )
    db.commit()
    db.refresh(approval)
    return approval
