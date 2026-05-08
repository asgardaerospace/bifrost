from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


# Canonical relationship types per BIFROST_ENTITY_SYSTEM / GRAPH_SYSTEM doctrine.
RELATIONSHIP_TYPES = (
    "depends_on",
    "blocks",
    "supports",
    "funds",
    "supplies",
    "owns",
    "affects",
    "influences",
    "participates_in",
    "relates_to",
    "mitigates",
    "escalates_to",
    "connected_to",
)


class Relationship(Base, TimestampMixin):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "relationship_type",
            name="uq_relationships_edge",
        ),
        Index("ix_relationships_source", "source_type", "source_id"),
        Index("ix_relationships_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
