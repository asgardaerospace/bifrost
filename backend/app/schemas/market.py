"""Pydantic schemas for Market OS."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from app.schemas.base import ORMModel, TimestampedRead


AccountType = Literal["prime", "startup", "supplier", "partner"]
CampaignStatus = Literal["active", "paused", "completed"]
AccountCampaignStatus = Literal[
    "not_contacted", "contacted", "responded", "engaged"
]
MarketOpportunityStage = Literal["identified", "exploring", "active", "closed"]


# --- Accounts -------------------------------------------------------------


class AccountBase(ORMModel):
    name: str = Field(min_length=1, max_length=255)
    sector: Optional[str] = None
    region: Optional[str] = None
    type: Optional[AccountType] = None
    website: Optional[str] = None
    notes: Optional[str] = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(ORMModel):
    name: Optional[str] = None
    sector: Optional[str] = None
    region: Optional[str] = None
    type: Optional[AccountType] = None
    website: Optional[str] = None
    notes: Optional[str] = None


class AccountRead(AccountBase, TimestampedRead):
    pass


# --- Account contacts -----------------------------------------------------


class AccountContactBase(ORMModel):
    account_id: int
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None


class AccountContactCreate(AccountContactBase):
    pass


class AccountContactUpdate(ORMModel):
    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None


class AccountContactRead(AccountContactBase, TimestampedRead):
    pass


# --- Campaigns ------------------------------------------------------------


class CampaignBase(ORMModel):
    name: str
    sector: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None
    status: CampaignStatus = "active"


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(ORMModel):
    name: Optional[str] = None
    sector: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CampaignStatus] = None


class CampaignRead(CampaignBase, TimestampedRead):
    pass


# --- Account/Campaign link ------------------------------------------------


class AccountCampaignBase(ORMModel):
    account_id: int
    campaign_id: int
    status: AccountCampaignStatus = "not_contacted"
    last_contacted_at: Optional[datetime] = None
    next_follow_up_at: Optional[datetime] = None


class AccountCampaignCreate(AccountCampaignBase):
    pass


class AccountCampaignUpdate(ORMModel):
    status: Optional[AccountCampaignStatus] = None
    last_contacted_at: Optional[datetime] = None
    next_follow_up_at: Optional[datetime] = None


class AccountCampaignRead(AccountCampaignBase, TimestampedRead):
    account_name: Optional[str] = None
    campaign_name: Optional[str] = None


# --- Market opportunities -------------------------------------------------


class MarketOpportunityBase(ORMModel):
    account_id: int
    name: str
    description: Optional[str] = None
    stage: MarketOpportunityStage = "identified"
    estimated_value: Optional[float] = None
    next_step: Optional[str] = None
    next_step_due_at: Optional[datetime] = None


class MarketOpportunityCreate(MarketOpportunityBase):
    pass


class MarketOpportunityUpdate(ORMModel):
    name: Optional[str] = None
    description: Optional[str] = None
    stage: Optional[MarketOpportunityStage] = None
    estimated_value: Optional[float] = None
    next_step: Optional[str] = None
    next_step_due_at: Optional[datetime] = None


class MarketOpportunityRead(MarketOpportunityBase, TimestampedRead):
    account_name: Optional[str] = None


# --- Dashboard summary ----------------------------------------------------


class MarketDashboardSummary(ORMModel):
    total_accounts: int
    active_campaigns: int
    active_opportunities: int
    accounts_needing_follow_up: int
