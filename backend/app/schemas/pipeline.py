from datetime import datetime
from typing import Optional

from app.schemas.base import ORMModel


class StageCount(ORMModel):
    stage: str
    count: int


class OpportunitySummary(ORMModel):
    id: int
    firm_id: int
    firm_name: Optional[str] = None
    stage: str
    status: str
    owner: Optional[str] = None
    next_step: Optional[str] = None
    next_step_due_at: Optional[datetime] = None
    fit_score: Optional[int] = None
    probability_score: Optional[int] = None
    strategic_value_score: Optional[int] = None
    last_interaction_at: Optional[datetime] = None
    days_since_last_interaction: Optional[int] = None
    priority_score: Optional[float] = None


class PipelineSummary(ORMModel):
    total_active: int
    stage_counts: list[StageCount]
    missing_next_step_count: int
    overdue_follow_up_count: int
    stale_count: int
    stale_threshold_days: int
    top_priority: list[OpportunitySummary]
    overdue_follow_ups: list[OpportunitySummary]
    stale_opportunities: list[OpportunitySummary]
