"""Program OS — execution layer connecting accounts, opportunities,
and (later) suppliers and investors.

A Program is a real contract, partnership, or pursuit. It always has
one owning account (``account_id``), optional additional accounts
through ``program_accounts`` (roles: prime/partner/customer), and a
future link to investor firms via ``program_investors``.
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


PROGRAM_STAGES = ("identified", "pursuing", "active", "won", "lost")
PROGRAM_ACCOUNT_ROLES = ("prime", "partner", "customer")
PROGRAM_INVESTOR_RELEVANCE = ("funding", "strategic", "observer")


class Program(Base, TimestampMixin):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(
        String(32), nullable=False, default="identified", index=True
    )
    estimated_value: Mapped[Optional[float]] = mapped_column(Numeric(18, 2))
    probability_score: Mapped[Optional[int]] = mapped_column(Integer)
    strategic_value_score: Mapped[Optional[int]] = mapped_column(Integer)
    owner: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    next_step: Mapped[Optional[str]] = mapped_column(Text)
    next_step_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    account: Mapped["Account"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Account"
    )
    account_links: Mapped[List["ProgramAccount"]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )
    investor_links: Mapped[List["ProgramInvestor"]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )
    activities: Mapped[List["ProgramActivity"]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )


class ProgramAccount(Base, TimestampMixin):
    __tablename__ = "program_accounts"
    __table_args__ = (
        UniqueConstraint(
            "program_id", "account_id", name="uq_program_accounts_pair"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    program: Mapped["Program"] = relationship(back_populates="account_links")


class ProgramInvestor(Base, TimestampMixin):
    __tablename__ = "program_investors"
    __table_args__ = (
        UniqueConstraint(
            "program_id", "investor_id", name="uq_program_investors_pair"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investor_id: Mapped[int] = mapped_column(
        ForeignKey("investor_firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relevance_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )

    program: Mapped["Program"] = relationship(back_populates="investor_links")


class ProgramActivity(Base, TimestampMixin):
    __tablename__ = "program_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    program: Mapped["Program"] = relationship(back_populates="activities")
