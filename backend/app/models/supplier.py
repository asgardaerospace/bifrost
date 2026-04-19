"""Supplier OS models — manufacturing network and program linkage."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


ONBOARDING_STATUSES = ("identified", "contacted", "qualified", "onboarded")
PROGRAM_SUPPLIER_ROLES = ("primary", "secondary", "backup")
PROGRAM_SUPPLIER_STATUSES = ("proposed", "engaged", "confirmed")
CERTIFICATION_STATUSES = ("active", "pending", "expired")


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    region: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    country: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    website: Mapped[Optional[str]] = mapped_column(String(512))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    onboarding_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="identified", index=True
    )
    preferred_partner_score: Mapped[Optional[int]] = mapped_column(Integer)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    capabilities: Mapped[List["SupplierCapability"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )
    certifications: Mapped[List["SupplierCertification"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )
    program_links: Mapped[List["ProgramSupplier"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )


class SupplierCapability(Base, TimestampMixin):
    __tablename__ = "supplier_capabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    capability_type: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text)

    supplier: Mapped["Supplier"] = relationship(back_populates="capabilities")


class SupplierCertification(Base, TimestampMixin):
    __tablename__ = "supplier_certifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    certification: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    expiration_date: Mapped[Optional[date]] = mapped_column(Date)

    supplier: Mapped["Supplier"] = relationship(back_populates="certifications")


class ProgramSupplier(Base, TimestampMixin):
    __tablename__ = "program_suppliers"
    __table_args__ = (
        UniqueConstraint(
            "program_id", "supplier_id", name="uq_program_suppliers_pair"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="proposed", index=True
    )

    supplier: Mapped["Supplier"] = relationship(back_populates="program_links")
