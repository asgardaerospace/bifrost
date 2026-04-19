"""Pydantic schemas for the pending_engine_writes outbox."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.schemas.base import ORMModel, TimestampedRead


class PendingEngineWriteRead(TimestampedRead):
    external_id: str
    action_type: str
    payload_json: dict[str, Any]
    status: str
    attempt_count: int
    last_error: Optional[str] = None
    idempotency_key: str
    engine_updated_at_snapshot: Optional[datetime] = None
    approval_id: Optional[int] = None
    requested_by: Optional[str] = None
    executed_at: Optional[datetime] = None


class EnqueueWriteRequest(ORMModel):
    """Operator-facing enqueue request.

    The approval gate is enforced by the caller — this schema is used
    by the service-layer enqueue helper and the dev/debug API.
    """

    action_type: str
    payload: dict[str, Any]
    requested_by: Optional[str] = None
    idempotency_key: Optional[str] = None
