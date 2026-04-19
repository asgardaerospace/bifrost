from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class InvestorFirm(Base, TimestampMixin):
    __tablename__ = "investor_firms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(512))
    stage_focus: Mapped[Optional[str]] = mapped_column(String(128))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="active", nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column()

    contacts: Mapped[List["InvestorContact"]] = relationship(
        back_populates="firm", cascade="all, delete-orphan"
    )
    opportunities: Mapped[List["InvestorOpportunity"]] = relationship(
        back_populates="firm", cascade="all, delete-orphan"
    )


class InvestorContact(Base, TimestampMixin):
    __tablename__ = "investor_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firm_id: Mapped[int] = mapped_column(
        ForeignKey("investor_firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(320), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(512))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    deleted_at: Mapped[Optional[datetime]] = mapped_column()

    firm: Mapped["InvestorFirm"] = relationship(back_populates="contacts")


class InvestorOpportunity(Base, TimestampMixin):
    __tablename__ = "investor_opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firm_id: Mapped[int] = mapped_column(
        ForeignKey("investor_firms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    primary_contact_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("investor_contacts.id", ondelete="SET NULL")
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="prospect")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="open")
    amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    target_close_date: Mapped[Optional[date]] = mapped_column(Date)
    summary: Mapped[Optional[str]] = mapped_column(Text)

    owner: Mapped[Optional[str]] = mapped_column(String(255))
    next_step: Mapped[Optional[str]] = mapped_column(Text)
    next_step_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    fit_score: Mapped[Optional[int]] = mapped_column(Integer)
    probability_score: Mapped[Optional[int]] = mapped_column(Integer)
    strategic_value_score: Mapped[Optional[int]] = mapped_column(Integer)

    deleted_at: Mapped[Optional[datetime]] = mapped_column()

    firm: Mapped["InvestorFirm"] = relationship(back_populates="opportunities")
    primary_contact: Mapped[Optional["InvestorContact"]] = relationship()
