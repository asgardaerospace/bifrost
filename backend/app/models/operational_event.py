from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


# Canonical bus topics from API_AND_SERVICE_ARCHITECTURE doctrine.
EVENT_TOPICS = (
    "missions",
    "intelligence",
    "execution",
    "graph",
    "memory",
    "agents",
    "presence",
    "approvals",
    "events",
)


class OperationalEvent(Base):
    """Bus-style event log for the realtime substrate.

    Distinct from `activity_events` (entity audit log). Operational events are
    fan-out signals for the awareness layer; persisted now, streamed in Sprint 2.
    """

    __tablename__ = "operational_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    mission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("missions.id", ondelete="SET NULL"), index=True
    )
    entity_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    actor: Mapped[Optional[str]] = mapped_column(String(255))
    source: Mapped[Optional[str]] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
