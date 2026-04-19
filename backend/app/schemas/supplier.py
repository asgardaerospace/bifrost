"""Pydantic schemas for Supplier OS."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import Field

from app.schemas.base import ORMModel, TimestampedRead


OnboardingStatus = Literal["identified", "contacted", "qualified", "onboarded"]
CertificationStatus = Literal["active", "pending", "expired"]
ProgramSupplierRole = Literal["primary", "secondary", "backup"]
ProgramSupplierStatus = Literal["proposed", "engaged", "confirmed"]


# --- suppliers ------------------------------------------------------------


class SupplierBase(ORMModel):
    name: str = Field(min_length=1, max_length=255)
    type: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None
    onboarding_status: OnboardingStatus = "identified"
    preferred_partner_score: Optional[int] = Field(default=None, ge=0, le=100)


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(ORMModel):
    name: Optional[str] = None
    type: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    notes: Optional[str] = None
    onboarding_status: Optional[OnboardingStatus] = None
    preferred_partner_score: Optional[int] = Field(default=None, ge=0, le=100)


class SupplierRead(SupplierBase, TimestampedRead):
    pass


# --- capabilities ---------------------------------------------------------


class SupplierCapabilityBase(ORMModel):
    supplier_id: int
    capability_type: str
    description: Optional[str] = None


class SupplierCapabilityCreate(SupplierCapabilityBase):
    pass


class SupplierCapabilityRead(SupplierCapabilityBase, TimestampedRead):
    pass


# --- certifications -------------------------------------------------------


class SupplierCertificationBase(ORMModel):
    supplier_id: int
    certification: str
    status: CertificationStatus = "active"
    expiration_date: Optional[date] = None


class SupplierCertificationCreate(SupplierCertificationBase):
    pass


class SupplierCertificationUpdate(ORMModel):
    certification: Optional[str] = None
    status: Optional[CertificationStatus] = None
    expiration_date: Optional[date] = None


class SupplierCertificationRead(SupplierCertificationBase, TimestampedRead):
    pass


# --- program <-> supplier links ------------------------------------------


class ProgramSupplierBase(ORMModel):
    program_id: int
    supplier_id: int
    role: ProgramSupplierRole
    status: ProgramSupplierStatus = "proposed"


class ProgramSupplierCreate(ProgramSupplierBase):
    pass


class ProgramSupplierUpdate(ORMModel):
    role: Optional[ProgramSupplierRole] = None
    status: Optional[ProgramSupplierStatus] = None


class ProgramSupplierRead(ProgramSupplierBase, TimestampedRead):
    supplier_name: Optional[str] = None
    program_name: Optional[str] = None


# --- supplier detail (hydrated) ------------------------------------------


class SupplierDetail(SupplierRead):
    capabilities: list[SupplierCapabilityRead] = []
    certifications: list[SupplierCertificationRead] = []
    program_links: list[ProgramSupplierRead] = []


# --- onboarding pipeline summary -----------------------------------------


class OnboardingPipelineSummary(ORMModel):
    total: int
    by_status: dict[str, int]
    qualified: int
    onboarded: int
    active_program_supplier_count: int
