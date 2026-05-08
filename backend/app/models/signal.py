"""Signal relevance + signal impact models.

Doctrine: intelligence is operational infrastructure. Signals propagate
through missions with explainable, deterministic, reversible scoring. The
relevance score per (signal, mission) is persisted with its decay trajectory
so retrieval and the relevance engine never recompute live unless a trigger
event fires.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SignalRelevance(Base, TimestampMixin):
    __tablename__ = "signal_relevance"
    __table_args__ = (
        UniqueConstraint(
            "intel_item_id", "mission_id", name="uq_signal_relevance_pair"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intel_item_id: Mapped[int] = mapped_column(
        ForeignKey("intel_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Raw computed score 0..100 at compute time.
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Score after recency decay applied. Index this for ranking.
    decayed_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, index=True
    )
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_relevant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SignalImpact(Base, TimestampMixin):
    __tablename__ = "signal_impact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intel_item_id: Mapped[int] = mapped_column(
        ForeignKey("intel_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mission_id: Mapped[int] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    impact_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    contribution: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
