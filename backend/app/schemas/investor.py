from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from app.schemas.base import ORMModel, TimestampedRead


class InvestorFirmBase(ORMModel):
    name: str
    website: Optional[str] = None
    stage_focus: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"


class InvestorFirmCreate(InvestorFirmBase):
    pass


class InvestorFirmUpdate(ORMModel):
    name: Optional[str] = None
    website: Optional[str] = None
    stage_focus: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class InvestorFirmRead(InvestorFirmBase, TimestampedRead):
    pass


class InvestorContactBase(ORMModel):
    firm_id: int
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    notes: Optional[str] = None


class InvestorContactCreate(InvestorContactBase):
    pass


class InvestorContactUpdate(ORMModel):
    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    notes: Optional[str] = None


class InvestorContactRead(InvestorContactBase, TimestampedRead):
    pass


class InvestorOpportunityBase(ORMModel):
    firm_id: int
    primary_contact_id: Optional[int] = None
    stage: str = "prospect"
    status: str = "open"
    amount: Optional[Decimal] = None
    target_close_date: Optional[date] = None
    summary: Optional[str] = None
    owner: Optional[str] = None
    next_step: Optional[str] = None
    next_step_due_at: Optional[datetime] = None
    fit_score: Optional[int] = None
    probability_score: Optional[int] = None
    strategic_value_score: Optional[int] = None


class InvestorOpportunityCreate(InvestorOpportunityBase):
    pass


class InvestorOpportunityUpdate(ORMModel):
    primary_contact_id: Optional[int] = None
    stage: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[Decimal] = None
    target_close_date: Optional[date] = None
    summary: Optional[str] = None
    owner: Optional[str] = None
    next_step: Optional[str] = None
    next_step_due_at: Optional[datetime] = None
    fit_score: Optional[int] = None
    probability_score: Optional[int] = None
    strategic_value_score: Optional[int] = None


class InvestorOpportunityRead(InvestorOpportunityBase, TimestampedRead):
    pass
