from datetime import datetime
from typing import Optional

from app.schemas.base import ORMModel
from app.schemas.communication import CommunicationRead
from app.schemas.pipeline import OpportunitySummary, PipelineSummary, StageCount
from app.schemas.workflow import WorkflowRunRead


class AgentPipelineSummary(ORMModel):
    total_active: int
    stage_counts: list[StageCount]
    missing_next_step_count: int
    overdue_follow_up_count: int
    stale_count: int
    stale_threshold_days: int
    top_priority: list[OpportunitySummary]
    overdue_follow_ups: list[OpportunitySummary]
    stale_opportunities: list[OpportunitySummary]
    narrative: str

    @classmethod
    def from_pipeline(cls, summary: PipelineSummary, *, narrative: str) -> "AgentPipelineSummary":
        return cls(
            total_active=summary.total_active,
            stage_counts=summary.stage_counts,
            missing_next_step_count=summary.missing_next_step_count,
            overdue_follow_up_count=summary.overdue_follow_up_count,
            stale_count=summary.stale_count,
            stale_threshold_days=summary.stale_threshold_days,
            top_priority=summary.top_priority,
            overdue_follow_ups=summary.overdue_follow_ups,
            stale_opportunities=summary.stale_opportunities,
            narrative=narrative,
        )


class PrioritizedOpportunity(ORMModel):
    opportunity: OpportunitySummary
    priority_score: float
    rationale: str
    recommended_next_action: str
    factors: list[str]


class PrioritizedOpportunitiesResponse(ORMModel):
    count: int
    generated_at: datetime
    results: list[PrioritizedOpportunity]


class TimelineHighlight(ORMModel):
    occurred_at: datetime
    item_type: str
    title: str
    summary: Optional[str] = None


class InvestorBrief(ORMModel):
    opportunity_id: int
    firm_id: int
    firm_name: Optional[str] = None
    firm_overview: Optional[str] = None
    primary_contact_id: Optional[int] = None
    primary_contact_name: Optional[str] = None
    primary_contact_email: Optional[str] = None
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
    blockers: list[str]
    recent_activity: list[TimelineHighlight]
    fit_assessment: str
    strategic_value_assessment: str
    recommended_executive_focus: str
    missing_context: list[str]
    generated_at: datetime


class AgentFollowUpDraftRequest(ORMModel):
    contact_id: Optional[int] = None
    intent: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    actor: Optional[str] = None


class AgentFollowUpDraftResponse(ORMModel):
    communication: CommunicationRead
    workflow_run: WorkflowRunRead
    rationale: str
    missing_context: list[str]
