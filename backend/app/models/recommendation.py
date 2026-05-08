"""Recommendation model — grounded operational recommendation with audit trail.

Doctrine: AI may recommend; humans decide. Every recommendation carries its
rationale, retrieval citations, confidence, projected impact, and the
operator's decision — fully auditable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    mission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("missions.id", ondelete="SET NULL"), index=True
    )
    target_entity_type: Mapped[Optional[str]] = mapped_column(String(64))
    target_entity_id: Mapped[Optional[int]] = mapped_column(Integer)

    projected_impact: Mapped[Optional[str]] = mapped_column(String(64))
    projected_delta: Mapped[Optional[int]] = mapped_column(Integer)

    # Free-form structured payload — scoring components, retrieval trace, etc.
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Retrieval citations (chunk_id, source_type, source_id, excerpt) for audit.
    citations: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSONB)

    source: Mapped[str] = mapped_column(String(64), nullable=False, default="engine")
    created_by: Mapped[Optional[str]] = mapped_column(String(255))

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    decided_by: Mapped[Optional[str]] = mapped_column(String(255))
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[Optional[str]] = mapped_column(Text)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
