"""Outbox table for queued investor engine mutations.

This table is the ONLY place where outbound writes to the investor
engine are staged. Every mutation goes through the flow:

    UI action -> approval -> enqueue row here -> worker -> engine

Nothing else in Bifrost is allowed to call the engine client's
mutation surface directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


# Status enum — string-valued for portability.
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"

# Supported action types.
ACTION_UPDATE_FOLLOW_UP = "update_follow_up"
ACTION_LOG_TOUCH = "log_touch"
ACTION_UPDATE_STAGE = "update_stage"

SUPPORTED_ACTIONS = frozenset(
    {ACTION_UPDATE_FOLLOW_UP, ACTION_LOG_TOUCH, ACTION_UPDATE_STAGE}
)


class PendingEngineWrite(Base, TimestampMixin):
    __tablename__ = "pending_engine_writes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    external_id: Mapped[str] = mapped_column(String(128), index=True)
    action_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(
        String(32), default=STATUS_PENDING, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, index=True
    )
    engine_updated_at_snapshot: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Link back to the approval that authorized this write (audit trail).
    approval_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    requested_by: Mapped[Optional[str]] = mapped_column(String(255))

    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
