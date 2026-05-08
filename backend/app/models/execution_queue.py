from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ExecutionQueueItem(Base, TimestampMixin):
    """Direct queue item store.

    The /execution/queue endpoint also projects existing tasks, approvals,
    pending drafts, and overdue investor opportunities into queue items at
    read time (see services/execution.py). Persisted rows here are for items
    that originate inside the queue itself (e.g., recommendations).
    """

    __tablename__ = "execution_queue_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    source_id: Mapped[Optional[int]] = mapped_column(Integer)

    mission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("missions.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", index=True
    )
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    pressure_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    owner: Mapped[Optional[str]] = mapped_column(String(255))
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    requires_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
