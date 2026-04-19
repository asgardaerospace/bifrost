"""Market OS core models — accounts, campaigns, opportunities.

Parallels the investor-side models but tracks target companies,
outreach campaigns, and market opportunities rather than capital.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


ACCOUNT_TYPES = ("prime", "startup", "supplier", "partner")
CAMPAIGN_STATUSES = ("active", "paused", "completed")
ACCOUNT_CAMPAIGN_STATUSES = (
    "not_contacted",
    "contacted",
    "responded",
    "engaged",
)
MARKET_OPPORTUNITY_STAGES = ("identified", "exploring", "active", "closed")


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sector: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    region: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    website: Mapped[Optional[str]] = mapped_column(String(512))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    contacts: Mapped[List["AccountContact"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    opportunities: Mapped[List["MarketOpportunity"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    campaign_links: Mapped[List["AccountCampaign"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class AccountContact(Base, TimestampMixin):
    __tablename__ = "account_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(320), index=True)
    linkedin: Mapped[Optional[str]] = mapped_column(String(512))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    account: Mapped["Account"] = relationship(back_populates="contacts")


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sector: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    region: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    account_links: Mapped[List["AccountCampaign"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class AccountCampaign(Base, TimestampMixin):
    __tablename__ = "account_campaigns"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "campaign_id", name="uq_account_campaigns_pair"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_contacted", index=True
    )
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    next_follow_up_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )

    account: Mapped["Account"] = relationship(back_populates="campaign_links")
    campaign: Mapped["Campaign"] = relationship(back_populates="account_links")


class MarketOpportunity(Base, TimestampMixin):
    __tablename__ = "market_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(
        String(32), nullable=False, default="identified", index=True
    )
    estimated_value: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    next_step: Mapped[Optional[str]] = mapped_column(Text)
    next_step_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    account: Mapped["Account"] = relationship(back_populates="opportunities")
