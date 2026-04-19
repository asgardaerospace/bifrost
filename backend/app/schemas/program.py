"""Pydantic schemas for Program OS."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from app.schemas.base import ORMModel, TimestampedRead


ProgramStage = Literal["identified", "pursuing", "active", "won", "lost"]
ProgramAccountRole = Literal["prime", "partner", "customer"]
ProgramInvestorRelevance = Literal["funding", "strategic", "observer"]


# --- programs -------------------------------------------------------------


class ProgramBase(ORMModel):
    name: str = Field(min_length=1, max_length=255)
    account_id: int
    description: Optional[str] = None
    stage: ProgramStage = "identified"
    estimated_value: Optional[float] = None
    probability_score: Optional[int] = Field(default=None, ge=0, le=100)
    strategic_value_score: Optional[int] = Field(default=None, ge=0, le=100)
    owner: Optional[str] = None
    next_step: Optional[str] = None
    next_step_due_at: Optional[datetime] = None


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(ORMModel):
    name: Optional[str] = None
    account_id: Optional[int] = None
    description: Optional[str] = None
    stage: Optional[ProgramStage] = None
    estimated_value: Optional[float] = None
    probability_score: Optional[int] = Field(default=None, ge=0, le=100)
    strategic_value_score: Optional[int] = Field(default=None, ge=0, le=100)
    owner: Optional[str] = None
    next_step: Optional[str] = None
    next_step_due_at: Optional[datetime] = None


class ProgramRead(ProgramBase, TimestampedRead):
    account_name: Optional[str] = None


# --- program <-> account --------------------------------------------------


class ProgramAccountBase(ORMModel):
    program_id: int
    account_id: int
    role: ProgramAccountRole


class ProgramAccountCreate(ProgramAccountBase):
    pass


class ProgramAccountRead(ProgramAccountBase, TimestampedRead):
    account_name: Optional[str] = None


# --- program <-> investor -------------------------------------------------


class ProgramInvestorBase(ORMModel):
    program_id: int
    investor_id: int
    relevance_type: ProgramInvestorRelevance


class ProgramInvestorCreate(ProgramInvestorBase):
    pass


class ProgramInvestorRead(ProgramInvestorBase, TimestampedRead):
    investor_name: Optional[str] = None


# --- program activities ---------------------------------------------------


class ProgramActivityCreate(ORMModel):
    program_id: int
    activity_type: str
    description: Optional[str] = None


class ProgramActivityRead(ProgramActivityCreate, TimestampedRead):
    pass


# --- pipeline summary -----------------------------------------------------


class ProgramStageCount(ORMModel):
    stage: str
    count: int


class ProgramPipelineSummary(ORMModel):
    total_programs: int
    active_count: int
    won_count: int
    lost_count: int
    stage_counts: list[ProgramStageCount]
    high_value_count: int
    high_value_threshold: float
    overdue_count: int
    total_estimated_value_active: float
    high_value: list[ProgramRead]
    overdue: list[ProgramRead]
