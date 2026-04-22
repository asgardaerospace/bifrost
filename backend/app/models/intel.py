"""Intelligence OS models — external news and market signals.

Intel is external by nature: items originate from curated third-party
sources, not from Bifrost operators. The schema therefore preserves
provenance (source, url, published_at) alongside classification
(category, scores) and structured tagging/actionability
(intel_entities, intel_tags, intel_actions).

Clear separation: nothing here links to internal entity tables via
foreign keys. When an intel item refers to an Asgard-tracked entity
(e.g. an investor firm or an account), we store the entity_type +
entity_name in intel_entities with an optional entity_id pointer —
that indirection keeps the intel stream auditable even if the
internal record is later removed or renamed.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


INTEL_CATEGORIES = (
    "vc_funding",
    "defense_tech",
    "space_systems",
    "aerospace_manufacturing",
    "supply_chain",
    "policy_procurement",
    "competitor_move",
    "partner_signal",
    "supplier_signal",
    "uncategorized",
)

INTEL_ENTITY_TYPES = (
    "company",
    "investor",
    "agency",
    "program",
    "person",
    "product",
    "country",
    "region",
)

INTEL_ENTITY_ROLES = (
    "primary",
    "investor",
    "investee",
    "acquirer",
    "acquiree",
    "partner",
    "competitor",
    "supplier",
    "customer",
    "regulator",
    "mentioned",
)

INTEL_ACTION_TYPES = (
    "watchlist",
    "review_investor",
    "review_account",
    "review_supplier",
    "review_program",
    "flag_competitor",
    "share_with_team",
    "archive",
)

INTEL_ACTION_STATUSES = (
    "pending",
    "acknowledged",
    "resolved",
    "dismissed",
)


class IntelItem(Base, TimestampMixin):
    __tablename__ = "intel_items"
    __table_args__ = (
        UniqueConstraint("source", "url", name="uq_intel_items_source_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1024))
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )
    region: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="uncategorized",
        index=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(Text)

    # Classification scores (0..100). Strategic/urgency from rule layer,
    # confidence reflects how strongly rules matched (vs. default/uncategorized).
    strategic_relevance_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, index=True
    )
    urgency_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    confidence_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    entities: Mapped[List["IntelEntity"]] = relationship(
        back_populates="intel_item", cascade="all, delete-orphan"
    )
    tags: Mapped[List["IntelTag"]] = relationship(
        back_populates="intel_item", cascade="all, delete-orphan"
    )
    actions: Mapped[List["IntelAction"]] = relationship(
        back_populates="intel_item", cascade="all, delete-orphan"
    )


class IntelEntity(Base):
    __tablename__ = "intel_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intel_item_id: Mapped[int] = mapped_column(
        ForeignKey("intel_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Nullable pointer into internal tables (accounts, investor_firms, ...).
    # Not a FK by design: the intel record must survive deletion of the
    # linked internal record.
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    role: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    intel_item: Mapped["IntelItem"] = relationship(back_populates="entities")


class IntelTag(Base):
    __tablename__ = "intel_tags"
    __table_args__ = (
        UniqueConstraint("intel_item_id", "tag", name="uq_intel_tags_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intel_item_id: Mapped[int] = mapped_column(
        ForeignKey("intel_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    intel_item: Mapped["IntelItem"] = relationship(back_populates="tags")


class IntelAction(Base, TimestampMixin):
    __tablename__ = "intel_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intel_item_id: Mapped[int] = mapped_column(
        ForeignKey("intel_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )

    intel_item: Mapped["IntelItem"] = relationship(back_populates="actions")
