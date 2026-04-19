"""Writer service for investor engine mutations.

Flow:
    enqueue()   — approval-gated creation of a pending_engine_writes row
    execute()   — transform payload, call client, update row status

Conflict detection: we compare the snapshot row's engine_updated_at
against the enqueued `engine_updated_at_snapshot`. If they diverge,
the engine has moved on since approval and we fail the write with a
"stale snapshot conflict" status — operator must re-approve.

This module is the ONLY place allowed to call
`InvestorEngineClient.apply_mutation`. Everything else must enqueue.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.investor_engine import client as engine_client
from app.integrations.investor_engine.models import InvestorEngineSnapshot
from app.integrations.investor_engine.writes_models import (
    ACTION_LOG_TOUCH,
    ACTION_UPDATE_FOLLOW_UP,
    ACTION_UPDATE_STAGE,
    PendingEngineWrite,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    STATUS_SUCCEEDED,
    SUPPORTED_ACTIONS,
)
from app.services.activity import log_activity

ENTITY_PENDING_WRITE = "pending_engine_write"
STALE_CONFLICT_REASON = "stale snapshot conflict"


class WriterError(Exception):
    pass


class DuplicateIdempotencyKey(WriterError):
    pass


class UnknownActionType(WriterError):
    pass


class SnapshotNotFound(WriterError):
    pass


def _load_snapshot(
    db: Session, external_id: str
) -> Optional[InvestorEngineSnapshot]:
    return db.execute(
        select(InvestorEngineSnapshot).where(
            InvestorEngineSnapshot.external_id == external_id
        )
    ).scalar_one_or_none()


def enqueue_write(
    db: Session,
    *,
    external_id: str,
    action_type: str,
    payload: dict[str, Any],
    approval_id: Optional[int] = None,
    requested_by: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> PendingEngineWrite:
    """Stage an outbound write. Does NOT call the engine."""
    if action_type not in SUPPORTED_ACTIONS:
        raise UnknownActionType(f"Unsupported action_type: {action_type!r}")

    snapshot = _load_snapshot(db, external_id)
    if snapshot is None:
        raise SnapshotNotFound(
            f"No engine snapshot for external_id={external_id!r}"
        )

    key = idempotency_key or uuid.uuid4().hex
    existing = db.execute(
        select(PendingEngineWrite).where(
            PendingEngineWrite.idempotency_key == key
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicateIdempotencyKey(
            f"A write with idempotency_key={key!r} already exists"
        )

    row = PendingEngineWrite(
        external_id=external_id,
        action_type=action_type,
        payload_json=dict(payload),
        status=STATUS_PENDING,
        attempt_count=0,
        idempotency_key=key,
        engine_updated_at_snapshot=snapshot.engine_updated_at,
        approval_id=approval_id,
        requested_by=requested_by,
    )
    db.add(row)
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_PENDING_WRITE,
        entity_id=row.id,
        event_type="engine_write.enqueued",
        summary=(
            f"Engine write '{action_type}' enqueued for {external_id}"
        ),
        actor=requested_by,
        details={
            "external_id": external_id,
            "action_type": action_type,
            "approval_id": approval_id,
            "idempotency_key": key,
        },
    )
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Payload transformation — map Bifrost payload shape to engine format.
# ---------------------------------------------------------------------------


def _transform_payload(action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Translate Bifrost payload vocabulary into engine-compatible keys.

    Kept in this module (rather than a mapper class) because the set is
    small. If it grows, split per action into its own module.
    """
    if action_type == ACTION_UPDATE_FOLLOW_UP:
        out: dict[str, Any] = {}
        if "next_follow_up_at" in payload:
            out["nextFollowUpAt"] = payload["next_follow_up_at"]
        if "follow_up_status" in payload:
            out["followUpStatus"] = payload["follow_up_status"]
        if "completed" in payload:
            out["followUpCompleted"] = bool(payload["completed"])
        return out
    if action_type == ACTION_LOG_TOUCH:
        return {
            "touchAt": payload.get("touch_at"),
            "channel": payload.get("channel"),
            "summary": payload.get("summary"),
            "author": payload.get("author"),
        }
    if action_type == ACTION_UPDATE_STAGE:
        return {
            "stage": payload.get("stage"),
            "nextStep": payload.get("next_step"),
        }
    raise UnknownActionType(f"Unsupported action_type: {action_type!r}")


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _mark_failed(
    db: Session,
    row: PendingEngineWrite,
    reason: str,
    *,
    increment_attempt: bool = True,
) -> None:
    row.status = STATUS_FAILED
    row.last_error = reason
    if increment_attempt:
        row.attempt_count = (row.attempt_count or 0) + 1
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_PENDING_WRITE,
        entity_id=row.id,
        event_type="engine_write.failed",
        summary=f"Engine write #{row.id} failed: {reason}",
        details={
            "external_id": row.external_id,
            "action_type": row.action_type,
            "error": reason,
        },
    )


def execute_write(
    db: Session,
    row: PendingEngineWrite,
    *,
    client: Optional[engine_client.InvestorEngineClient] = None,
) -> PendingEngineWrite:
    """Execute a single pending write.

    Behaviour:
        - re-loads the snapshot, checks engine_updated_at
        - transitions pending -> processing
        - calls the engine client
        - transitions to succeeded or failed
    """
    if row.status not in (STATUS_PENDING, STATUS_FAILED):
        # Already terminal or mid-processing. No-op.
        return row

    # Conflict detection: compare enqueued snapshot vs current snapshot.
    snapshot = _load_snapshot(db, row.external_id)
    if snapshot is None:
        _mark_failed(db, row, "snapshot missing")
        db.commit()
        db.refresh(row)
        return row

    enqueued_at = row.engine_updated_at_snapshot
    current_at = snapshot.engine_updated_at
    if enqueued_at != current_at:
        _mark_failed(db, row, STALE_CONFLICT_REASON)
        db.commit()
        db.refresh(row)
        return row

    row.status = STATUS_PROCESSING
    row.attempt_count = (row.attempt_count or 0) + 1
    db.flush()
    db.commit()
    db.refresh(row)

    try:
        engine_payload = _transform_payload(row.action_type, row.payload_json)
    except UnknownActionType as exc:
        _mark_failed(db, row, str(exc), increment_attempt=False)
        db.commit()
        db.refresh(row)
        return row

    cli = client or engine_client.get_default_client()
    try:
        result = cli.apply_mutation(
            external_id=row.external_id,
            action_type=row.action_type,
            payload=engine_payload,
            idempotency_key=row.idempotency_key,
        )
    except Exception as exc:  # boundary; translate to failed status
        _mark_failed(db, row, f"client raised: {exc}", increment_attempt=False)
        db.commit()
        db.refresh(row)
        return row

    if not result.success:
        _mark_failed(
            db,
            row,
            result.error or "engine rejected mutation",
            increment_attempt=False,
        )
        db.commit()
        db.refresh(row)
        return row

    row.status = STATUS_SUCCEEDED
    row.last_error = None
    row.executed_at = datetime.now(timezone.utc)

    # Opportunistically advance the snapshot's engine_updated_at so
    # subsequent enqueues are consistent; the next sync will fully
    # refresh the row.
    if result.engine_updated_at is not None:
        snapshot.engine_updated_at = result.engine_updated_at

    log_activity(
        db,
        entity_type=ENTITY_PENDING_WRITE,
        entity_id=row.id,
        event_type="engine_write.succeeded",
        summary=(
            f"Engine write '{row.action_type}' succeeded for {row.external_id}"
        ),
        details={
            "external_id": row.external_id,
            "action_type": row.action_type,
            "response": result.response,
        },
    )
    db.commit()
    db.refresh(row)
    return row
