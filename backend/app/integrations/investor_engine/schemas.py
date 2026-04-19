"""Pydantic schemas mirroring the external investor engine payload.

These models intentionally describe the *foreign* shape. They are kept
separate from `app.schemas.investor` so that any changes upstream stay
contained in this module.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _EngineModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class EngineContact(_EngineModel):
    external_id: str = Field(..., alias="id")
    full_name: str = Field(..., alias="name")
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = Field(default=None, alias="linkedin")
    notes: Optional[str] = None


class EngineActivity(_EngineModel):
    """A single engine activity event (email, call, meeting, note)."""

    external_id: str = Field(..., alias="id")
    kind: str = Field(..., alias="type")
    summary: Optional[str] = None
    occurred_at: Optional[datetime] = Field(default=None, alias="timestamp")
    author: Optional[str] = None


class EngineInvestor(_EngineModel):
    """Top-level investor record coming from the engine.

    One `EngineInvestor` maps to a Bifrost firm plus its opportunity
    plus its contacts. The engine flattens firm + deal, Bifrost splits
    them — the mapper is where that translation happens.
    """

    external_id: str = Field(..., alias="id")
    firm_name: str = Field(..., alias="name")
    website: Optional[str] = None
    stage_focus: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

    # pipeline / execution fields
    stage: Optional[str] = None
    follow_up_status: Optional[str] = Field(default=None, alias="followUpStatus")
    last_touch_at: Optional[datetime] = Field(default=None, alias="lastTouch")
    next_follow_up_at: Optional[datetime] = Field(default=None, alias="nextFollowUp")
    next_step: Optional[str] = Field(default=None, alias="nextStep")
    owner: Optional[str] = None

    amount: Optional[Decimal] = None
    target_close_date: Optional[date] = Field(default=None, alias="targetCloseDate")
    fit_score: Optional[int] = Field(default=None, alias="fitScore")
    probability_score: Optional[int] = Field(default=None, alias="probabilityScore")
    strategic_value_score: Optional[int] = Field(
        default=None, alias="strategicValueScore"
    )

    contacts: List[EngineContact] = Field(default_factory=list)
    activity: List[EngineActivity] = Field(default_factory=list)

    # engine-side bookkeeping
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")


class EnginePayload(_EngineModel):
    """The root payload shape returned by the engine for a full pull."""

    investors: List[EngineInvestor] = Field(default_factory=list)
    generated_at: Optional[datetime] = Field(default=None, alias="generatedAt")
