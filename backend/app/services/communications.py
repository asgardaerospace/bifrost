"""Follow-up drafting and send-approval request services.

State transitions owned here:
    Communication:  draft  --request_send-->  pending_approval
    Communication:  pending_approval  --approve+send-->  sent
    Communication:  pending_approval  --reject-->       draft

Drafts may be created freely. Sending always requires an Approval.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.communication import Communication
from app.models.investor import InvestorContact, InvestorFirm
from app.models.workflow import WorkflowRun
from app.schemas.workflows import FollowUpDraftRequest
from app.services import investor as investor_service
from app.services.activity import log_activity

ENTITY_OPPORTUNITY = "investor_opportunity"
ENTITY_COMMUNICATION = "communication"

WORKFLOW_FOLLOW_UP_DRAFT = "investor.follow_up_draft"
WORKFLOW_SEND_APPROVAL = "investor.send_approval"

STATUS_DRAFT = "draft"
STATUS_PENDING_APPROVAL = "pending_approval"
STATUS_SENT = "sent"

APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"

ACTION_SEND_COMMUNICATION = "send_communication"


def _placeholder_draft(
    firm: InvestorFirm, contact: Optional[InvestorContact]
) -> tuple[str, str]:
    """Deterministic placeholder content when no generator is wired.

    LLM generation is intentionally not invoked here; the draft workflow
    exists so a human-authored or agent-authored body can be written to
    the Communication before sending. An agent hook can replace this.
    """
    subject = f"Following up — {firm.name}"
    addressee = contact.name.split()[0] if contact and contact.name else "team"
    body = (
        f"Hi {addressee},\n\n"
        f"Following up on our conversation regarding Asgard and "
        f"{firm.name}. Let me know a good time to continue the discussion.\n\n"
        f"Best,\nAsgard"
    )
    return subject, body


def _resolve_contact(
    db: Session, opp_firm_id: int, contact_id: Optional[int]
) -> Optional[InvestorContact]:
    if contact_id is None:
        return None
    contact = investor_service.get_contact(db, contact_id)
    if contact.firm_id != opp_firm_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact does not belong to the opportunity's firm",
        )
    return contact


def create_follow_up_draft(
    db: Session,
    opportunity_id: int,
    payload: FollowUpDraftRequest,
) -> tuple[Communication, WorkflowRun]:
    opp = investor_service.get_opportunity(db, opportunity_id)
    firm = db.get(InvestorFirm, opp.firm_id)
    if firm is None:
        raise HTTPException(status_code=404, detail="Firm not found")

    contact_id = payload.contact_id or opp.primary_contact_id
    contact = _resolve_contact(db, opp.firm_id, contact_id)

    now = datetime.now(timezone.utc)
    run = WorkflowRun(
        workflow_key=WORKFLOW_FOLLOW_UP_DRAFT,
        entity_type=ENTITY_OPPORTUNITY,
        entity_id=opp.id,
        status="in_progress",
        triggered_by=payload.actor,
        started_at=now,
        input_payload={
            "opportunity_id": opp.id,
            "firm_id": firm.id,
            "contact_id": contact.id if contact else None,
            "has_user_body": payload.body is not None,
        },
    )
    db.add(run)
    db.flush()

    default_subject, default_body = _placeholder_draft(firm, contact)
    subject = payload.subject or default_subject
    body = payload.body or default_body

    to_address = payload.to_address or (contact.email if contact else None)

    comm = Communication(
        entity_type=ENTITY_OPPORTUNITY,
        entity_id=opp.id,
        channel="email",
        direction="outbound",
        status=STATUS_DRAFT,
        subject=subject,
        body=body,
        from_address=payload.from_address,
        to_address=to_address,
    )
    db.add(comm)
    db.flush()

    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    run.result_payload = {"communication_id": comm.id}
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_OPPORTUNITY,
        entity_id=opp.id,
        event_type="investor_opportunity.follow_up_drafted",
        summary=f"Follow-up draft created for '{firm.name}'",
        actor=payload.actor,
        details={
            "communication_id": comm.id,
            "workflow_run_id": run.id,
            "contact_id": contact.id if contact else None,
        },
    )

    db.commit()
    db.refresh(comm)
    db.refresh(run)
    return comm, run


def request_send_approval(
    db: Session,
    communication_id: int,
    *,
    requested_by: Optional[str] = None,
    note: Optional[str] = None,
) -> Approval:
    comm = db.get(Communication, communication_id)
    if comm is None or comm.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Communication not found")
    if comm.status != STATUS_DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Communication must be in '{STATUS_DRAFT}' to request approval (current: '{comm.status}')",
        )

    now = datetime.now(timezone.utc)
    run = WorkflowRun(
        workflow_key=WORKFLOW_SEND_APPROVAL,
        entity_type=ENTITY_COMMUNICATION,
        entity_id=comm.id,
        status="pending",
        triggered_by=requested_by,
        started_at=now,
        input_payload={"communication_id": comm.id, "note": note},
    )
    db.add(run)
    db.flush()

    approval = Approval(
        entity_type=ENTITY_COMMUNICATION,
        entity_id=comm.id,
        workflow_run_id=run.id,
        action=ACTION_SEND_COMMUNICATION,
        status=APPROVAL_PENDING,
        requested_by=requested_by,
        decision_note=note,
    )
    db.add(approval)
    db.flush()

    comm.status = STATUS_PENDING_APPROVAL
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_COMMUNICATION,
        entity_id=comm.id,
        event_type="communication.send_approval_requested",
        summary=f"Send approval requested for communication #{comm.id}",
        actor=requested_by,
        details={"approval_id": approval.id, "workflow_run_id": run.id},
    )

    db.commit()
    db.refresh(approval)
    return approval
