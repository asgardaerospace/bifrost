"""Memory + semantic chunk models.

Doctrine: organizational memory is the substrate that grounds AI reasoning.
Memory records are append-mostly (versioned, soft-deleted), and chunks are
fully derived from records — they may be regenerated whenever a record's
source_hash changes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin


# Stored as JSON on both Postgres and SQLite. Postgres-side `vector(N)` swap
# is a Sprint 4+ optimization once dataset size justifies in-DB similarity.
EMBEDDING_DIM = 1536


class MemoryRecord(Base, TimestampMixin):
    __tablename__ = "memory_records"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_memory_records_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text, nullable=False)

    mission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("missions.id", ondelete="SET NULL"), index=True
    )
    entity_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(255))

    source_occurred_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    embedding_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    embedded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    chunks: Mapped[List["SemanticChunk"]] = relationship(
        back_populates="record", cascade="all, delete-orphan"
    )


class SemanticChunk(Base):
    __tablename__ = "semantic_chunks"
    __table_args__ = (
        UniqueConstraint(
            "memory_record_id", "chunk_index", name="uq_semantic_chunks_record_idx"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    memory_record_id: Mapped[int] = mapped_column(
        ForeignKey("memory_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Stored as JSON list of floats. Cross-DB compatible. Sprint 4 candidate
    # for migration to pgvector `vector(N)` for index-backed similarity.
    embedding: Mapped[Optional[list[float]]] = mapped_column(JSON)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(128))
    embedding_dim: Mapped[Optional[int]] = mapped_column(Integer)

    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    record: Mapped["MemoryRecord"] = relationship(back_populates="chunks")
