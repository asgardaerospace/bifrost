"""Create Bifrost-side follow-up drafts from investor engine records.

Engine records do not live in Bifrost's native investor tables, so
`communications.create_follow_up_draft` (which requires an
`investor_opportunity` id) cannot be used directly. This module
mirrors that service but anchors the draft to the engine snapshot
row and stamps source provenance.

Provenance is carried on the Communication itself via:
    source_system      = "investor_engine"
    source_external_id = <NormalizedInvestor.external_id>

`entity_type` / `entity_id` point at the snapshot row so the rest of
Bifrost (activity log, timelines) can still reason about it using the
standard generic-entity pattern.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.investor_engine.mapper import NormalizedInvestor
from app.integrations.investor_engine.models import InvestorEngineSnapshot
from app.models.communication import Communication
from app.models.workflow import WorkflowRun
from app.services.activity import log_activity

SOURCE_SYSTEM = "investor_engine"
ENTITY_ENGINE_SNAPSHOT = "investor_engine_snapshot"
WORKFLOW_ENGINE_FOLLOW_UP_DRAFT = "investor_engine.follow_up_draft"
STATUS_DRAFT = "draft"


class EngineFollowUpDraftRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    actor: Optional[str] = None


def _placeholder(normalized: NormalizedInvestor) -> tuple[str, str]:
    contact = normalized.contacts[0] if normalized.contacts else None
    addressee = (
        contact.name.split()[0] if contact and contact.name else "team"
    )
    subject = f"Following up — {normalized.firm_name}"
    stage_line = (
        f"You're currently tracked at stage '{normalized.stage}'. "
        if normalized.stage
        else ""
    )
    next_step_line = (
        f"Next step on our side: {normalized.next_step}. "
        if normalized.next_step
        else ""
    )
    body = (
        f"Hi {addressee},\n\n"
        f"Following up on our conversation regarding Asgard and "
        f"{normalized.firm_name}. {stage_line}{next_step_line}"
        f"Let me know a good time to continue.\n\n"
        f"Best,\nAsgard"
    )
    return subject, body


def _load_snapshot(db: Session, external_id: str) -> InvestorEngineSnapshot:
    snap = db.execute(
        select(InvestorEngineSnapshot).where(
            InvestorEngineSnapshot.external_id == external_id
        )
    ).scalar_one_or_none()
    if snap is None:
        raise HTTPException(
            status_code=404,
            detail=f"No investor engine record with external_id={external_id!r}",
        )
    return snap


def create_engine_follow_up_draft(
    db: Session,
    external_id: str,
    payload: EngineFollowUpDraftRequest,
) -> tuple[Communication, WorkflowRun]:
    snapshot = _load_snapshot(db, external_id)
    normalized = NormalizedInvestor.model_validate(snapshot.payload)

    now = datetime.now(timezone.utc)
    run = WorkflowRun(
        workflow_key=WORKFLOW_ENGINE_FOLLOW_UP_DRAFT,
        entity_type=ENTITY_ENGINE_SNAPSHOT,
        entity_id=snapshot.id,
        status="in_progress",
        triggered_by=payload.actor,
        started_at=now,
        input_payload={
            "source_system": SOURCE_SYSTEM,
            "source_external_id": normalized.external_id,
            "firm_name": normalized.firm_name,
            "has_user_body": payload.body is not None,
        },
    )
    db.add(run)
    db.flush()

    default_subject, default_body = _placeholder(normalized)
    subject = payload.subject or default_subject
    body = payload.body or default_body

    primary_contact = normalized.contacts[0] if normalized.contacts else None
    to_address = payload.to_address or (
        primary_contact.email if primary_contact else None
    )

    comm = Communication(
        entity_type=ENTITY_ENGINE_SNAPSHOT,
        entity_id=snapshot.id,
        channel="email",
        direction="outbound",
        status=STATUS_DRAFT,
        subject=subject,
        body=body,
        from_address=payload.from_address,
        to_address=to_address,
        source_system=SOURCE_SYSTEM,
        source_external_id=normalized.external_id,
    )
    db.add(comm)
    db.flush()

    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    run.result_payload = {"communication_id": comm.id}
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_ENGINE_SNAPSHOT,
        entity_id=snapshot.id,
        event_type="investor_engine.follow_up_drafted",
        summary=(
            f"Follow-up draft created from investor engine record "
            f"'{normalized.firm_name}' ({normalized.external_id})"
        ),
        actor=payload.actor,
        details={
            "communication_id": comm.id,
            "workflow_run_id": run.id,
            "source_system": SOURCE_SYSTEM,
            "source_external_id": normalized.external_id,
        },
    )

    db.commit()
    db.refresh(comm)
    db.refresh(run)
    return comm, run
