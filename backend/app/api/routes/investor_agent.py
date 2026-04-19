from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.investor_agent import (
    AgentFollowUpDraftRequest,
    AgentFollowUpDraftResponse,
    AgentPipelineSummary,
    InvestorBrief,
    PrioritizedOpportunitiesResponse,
)
from app.services import investor_agent as agent_service

router = APIRouter()


@router.get("/pipeline-summary", response_model=AgentPipelineSummary)
def pipeline_summary(
    stale_threshold_days: int = Query(21, ge=1, le=365),
    top_priority_limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AgentPipelineSummary:
    return agent_service.build_agent_pipeline_summary(
        db,
        stale_threshold_days=stale_threshold_days,
        top_priority_limit=top_priority_limit,
    )


@router.get(
    "/prioritized-opportunities", response_model=PrioritizedOpportunitiesResponse
)
def prioritized_opportunities(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PrioritizedOpportunitiesResponse:
    return agent_service.prioritize_opportunities(db, limit=limit)


@router.get("/opportunities/{opportunity_id}/brief", response_model=InvestorBrief)
def opportunity_brief(
    opportunity_id: int, db: Session = Depends(get_db)
) -> InvestorBrief:
    return agent_service.build_investor_brief(db, opportunity_id)


@router.post(
    "/opportunities/{opportunity_id}/follow-up-draft",
    response_model=AgentFollowUpDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def follow_up_draft(
    opportunity_id: int,
    payload: AgentFollowUpDraftRequest,
    db: Session = Depends(get_db),
) -> AgentFollowUpDraftResponse:
    return agent_service.orchestrate_follow_up_draft(db, opportunity_id, payload)
