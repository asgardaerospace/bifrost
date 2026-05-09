"""Governance — approvals ↔ execution queue ↔ proposed actions.

Doctrine (AUTONOMY_GOVERNANCE / SECURITY_AND_GOVERNANCE):
  * Every autonomous operation must remain visible, auditable, explainable,
    reversible.
  * Approval-required actions must not execute directly — they must transit
    through an Approval row owned by a human reviewer.

This service encapsulates the polymorphic Approval coupling for the new
mission-aware queue + autonomy ledger:
  * Approval(entity_type='execution_queue_item', entity_id=N)
  * Approval(entity_type='proposed_action', entity_id=N)

The legacy communication-approval flow (services/approvals.py) is untouched.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.autonomy import ProposedAction
from app.models.execution_queue import ExecutionQueueItem
from app.schemas.operational_event import OperationalEventCreate
from app.services import audit as audit_service
from app.services import events as events_service
from app.services import memory as memory_service
from app.services import pressure as pressure_service


# Polymorphic entity_type constants used for queue/autonomy approvals.
ENTITY_QUEUE_ITEM = "execution_queue_item"
ENTITY_PROPOSED_ACTION = "proposed_action"

# Approval action verbs (extends comm_service constants without conflicting).
ACTION_COMPLETE_QUEUE_ITEM = "execute_queue_item"
ACTION_EXECUTE_PROPOSED = "execute_proposed_action"

APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------


def find_approval_for(
    db: Session, *, entity_type: str, entity_id: int
) -> Optional[Approval]:
    """Latest approval row attached to a polymorphic entity (any status)."""
    return db.scalars(
        select(Approval)
        .where(Approval.entity_type == entity_type)
        .where(Approval.entity_id == entity_id)
        .order_by(Approval.created_at.desc())
    ).first()


def is_authorized_to_complete_queue_item(
    db: Session, item: ExecutionQueueItem
) -> bool:
    """A queue item that requires approval may only complete after the latest
    Approval(entity='execution_queue_item') is in status='approved'."""
    if not item.requires_approval:
        return True
    approval = find_approval_for(
        db, entity_type=ENTITY_QUEUE_ITEM, entity_id=item.id
    )
    return approval is not None and approval.status == APPROVAL_APPROVED


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def request_queue_item_approval(
    db: Session,
    item: ExecutionQueueItem,
    *,
    requested_by: str,
    note: Optional[str] = None,
) -> Approval:
    """Create or refresh a pending Approval for a queue item.

    Idempotent for pending state — calling twice on the same item with no
    in-flight resolution returns the existing pending row.
    """
    existing = find_approval_for(
        db, entity_type=ENTITY_QUEUE_ITEM, entity_id=item.id
    )
    if existing is not None and existing.status == APPROVAL_PENDING:
        return existing

    approval = Approval(
        entity_type=ENTITY_QUEUE_ITEM,
        entity_id=item.id,
        action=ACTION_COMPLETE_QUEUE_ITEM,
        status=APPROVAL_PENDING,
        requested_by=requested_by,
        decision_note=note,
        mission_id=item.mission_id,
    )
    db.add(approval)
    db.flush()

    events_service.publish(
        db,
        OperationalEventCreate(
            topic="approvals",
            event_type="approval.requested",
            mission_id=item.mission_id,
            entity_type=ENTITY_QUEUE_ITEM,
            entity_id=item.id,
            actor=requested_by,
            severity="notice",
            payload={
                "approval_id": approval.id,
                "queue_item_title": item.title,
                "queue_item_type": item.item_type,
            },
        ),
    )
    return approval


def request_proposed_action_approval(
    db: Session,
    action: ProposedAction,
    *,
    requested_by: str,
    note: Optional[str] = None,
) -> Approval:
    """Create a pending Approval for a ProposedAction (autonomy ledger)."""
    existing = find_approval_for(
        db, entity_type=ENTITY_PROPOSED_ACTION, entity_id=action.id
    )
    if existing is not None and existing.status == APPROVAL_PENDING:
        return existing

    approval = Approval(
        entity_type=ENTITY_PROPOSED_ACTION,
        entity_id=action.id,
        action=ACTION_EXECUTE_PROPOSED,
        status=APPROVAL_PENDING,
        requested_by=requested_by,
        decision_note=note,
    )
    db.add(approval)
    db.flush()

    events_service.publish(
        db,
        OperationalEventCreate(
            topic="approvals",
            event_type="approval.requested",
            entity_type=ENTITY_PROPOSED_ACTION,
            entity_id=action.id,
            actor=requested_by,
            severity="notice",
            payload={
                "approval_id": approval.id,
                "action_type": action.action_type,
                "autonomy_operation_id": action.autonomy_operation_id,
            },
        ),
    )
    return approval


# ---------------------------------------------------------------------------
# decisions (decoupled from the legacy communication flow)
# ---------------------------------------------------------------------------


def decide(
    db: Session,
    approval_id: int,
    *,
    decision: str,  # "approved" | "rejected"
    reviewer: str,
    note: Optional[str] = None,
) -> Approval:
    if decision not in (APPROVAL_APPROVED, APPROVAL_REJECTED):
        raise HTTPException(status_code=422, detail="decision must be approved|rejected")

    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != APPROVAL_PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Approval is not pending (current: '{approval.status}')",
        )
    # Only handle queue item / proposed action approvals — leave the
    # communication-specific path to services/approvals.py.
    if approval.entity_type not in (ENTITY_QUEUE_ITEM, ENTITY_PROPOSED_ACTION):
        raise HTTPException(
            status_code=400,
            detail=(
                "governance.decide handles execution_queue_item and "
                "proposed_action approvals; route communication approvals "
                "through /approvals/{id}/approve which uses services/approvals.py"
            ),
        )

    now = datetime.now(timezone.utc)
    approval.status = decision
    approval.reviewer = reviewer
    approval.reviewed_at = now
    if note is not None:
        approval.decision_note = note
    db.flush()

    # Cascade: when a proposed action is approved, mark it approved (still
    # not executed — that's a later step in autonomy_orchestration).
    if approval.entity_type == ENTITY_PROPOSED_ACTION and decision == APPROVAL_APPROVED:
        action = db.get(ProposedAction, approval.entity_id)
        if action is not None and action.status == "pending":
            action.status = "approved"
            db.flush()

    event = events_service.publish(
        db,
        OperationalEventCreate(
            topic="approvals",
            event_type=f"approval.{decision}",
            mission_id=approval.mission_id,
            entity_type=approval.entity_type,
            entity_id=approval.entity_id,
            actor=reviewer,
            severity="notice" if decision == APPROVAL_APPROVED else "warning",
            payload={
                "approval_id": approval.id,
                "action": approval.action,
                "note": note,
            },
        ),
    )
    pressure_service.recompute_for_mission(
        db, approval.mission_id, source="trigger", trigger_event_id=event.id
    )
    try:
        memory_service.ingest_approval(db, approval)
    except Exception:
        pass

    audit_service.record(
        db,
        action=audit_service.ACTION_APPROVAL_DECIDE,
        actor=reviewer,
        outcome=decision,
        mission_id=approval.mission_id,
        target_type=approval.entity_type,
        target_id=approval.entity_id,
        detail={
            "approval_id": approval.id,
            "approval_action": approval.action,
            "note": note,
        },
        severity="warning" if decision == APPROVAL_REJECTED else "notice",
    )

    db.commit()
    db.refresh(approval)
    return approval
