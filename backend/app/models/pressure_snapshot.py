from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MissionPressureSnapshot(Base):
    """Persisted pressure history for a mission.

    Doctrine: pressure must be deterministic, transparent, and explainable.
    Each snapshot stores the full component breakdown (`components` JSONB)
    plus the discrete counts that fed it, so the operator can audit any
    historical reading.
    """

    __tablename__ = "mission_pressure_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    health_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="nominal"
    )
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    blockers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overdue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_approvals_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    unresolved_dependencies_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    high_priority_intel_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    activity_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    escalation_flags_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    source: Mapped[str] = mapped_column(String(32), nullable=False, default="trigger")
    trigger_event_id: Mapped[Optional[int]] = mapped_column(Integer)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
