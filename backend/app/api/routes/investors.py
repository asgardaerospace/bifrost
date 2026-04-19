from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.investor import (
    InvestorContactCreate,
    InvestorContactRead,
    InvestorContactUpdate,
    InvestorFirmCreate,
    InvestorFirmRead,
    InvestorFirmUpdate,
    InvestorOpportunityCreate,
    InvestorOpportunityRead,
    InvestorOpportunityUpdate,
)
from app.schemas.pipeline import OpportunitySummary, PipelineSummary
from app.schemas.timeline import TimelineResponse
from app.schemas.workflows import FollowUpDraftRequest, FollowUpDraftResponse
from app.services import communications as communications_service
from app.services import investor as investor_service
from app.services import pipeline as pipeline_service
from app.services import timeline as timeline_service

router = APIRouter()


# ---------------------------------------------------------------------------
# firms
# ---------------------------------------------------------------------------

@router.post(
    "/firms",
    response_model=InvestorFirmRead,
    status_code=status.HTTP_201_CREATED,
)
def create_firm(
    payload: InvestorFirmCreate,
    db: Session = Depends(get_db),
) -> InvestorFirmRead:
    return investor_service.create_firm(db, payload)


@router.get("/firms", response_model=list[InvestorFirmRead])
def list_firms(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> list[InvestorFirmRead]:
    return investor_service.list_firms(
        db, skip=skip, limit=limit, include_deleted=include_deleted
    )


@router.get("/firms/{firm_id}", response_model=InvestorFirmRead)
def get_firm(firm_id: int, db: Session = Depends(get_db)) -> InvestorFirmRead:
    return investor_service.get_firm(db, firm_id)


@router.patch("/firms/{firm_id}", response_model=InvestorFirmRead)
def update_firm(
    firm_id: int,
    payload: InvestorFirmUpdate,
    db: Session = Depends(get_db),
) -> InvestorFirmRead:
    return investor_service.update_firm(db, firm_id, payload)


@router.delete("/firms/{firm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_firm(firm_id: int, db: Session = Depends(get_db)) -> Response:
    investor_service.delete_firm(db, firm_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# contacts
# ---------------------------------------------------------------------------

@router.post(
    "/contacts",
    response_model=InvestorContactRead,
    status_code=status.HTTP_201_CREATED,
)
def create_contact(
    payload: InvestorContactCreate,
    db: Session = Depends(get_db),
) -> InvestorContactRead:
    return investor_service.create_contact(db, payload)


@router.get("/contacts", response_model=list[InvestorContactRead])
def list_contacts(
    firm_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> list[InvestorContactRead]:
    return investor_service.list_contacts(
        db,
        firm_id=firm_id,
        skip=skip,
        limit=limit,
        include_deleted=include_deleted,
    )


@router.get("/contacts/{contact_id}", response_model=InvestorContactRead)
def get_contact(contact_id: int, db: Session = Depends(get_db)) -> InvestorContactRead:
    return investor_service.get_contact(db, contact_id)


@router.patch("/contacts/{contact_id}", response_model=InvestorContactRead)
def update_contact(
    contact_id: int,
    payload: InvestorContactUpdate,
    db: Session = Depends(get_db),
) -> InvestorContactRead:
    return investor_service.update_contact(db, contact_id, payload)


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, db: Session = Depends(get_db)) -> Response:
    investor_service.delete_contact(db, contact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# opportunities
# ---------------------------------------------------------------------------

@router.post(
    "/opportunities",
    response_model=InvestorOpportunityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_opportunity(
    payload: InvestorOpportunityCreate,
    db: Session = Depends(get_db),
) -> InvestorOpportunityRead:
    return investor_service.create_opportunity(db, payload)


@router.get("/opportunities", response_model=list[InvestorOpportunityRead])
def list_opportunities(
    firm_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> list[InvestorOpportunityRead]:
    return investor_service.list_opportunities(
        db,
        firm_id=firm_id,
        status_filter=status_filter,
        skip=skip,
        limit=limit,
        include_deleted=include_deleted,
    )


@router.get("/opportunities/pipeline/summary", response_model=PipelineSummary)
def pipeline_summary(
    stale_threshold_days: int = Query(21, ge=1, le=365),
    top_priority_limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PipelineSummary:
    return pipeline_service.build_pipeline_summary(
        db,
        stale_threshold_days=stale_threshold_days,
        top_priority_limit=top_priority_limit,
    )


@router.get(
    "/opportunities/pipeline/overdue", response_model=list[OpportunitySummary]
)
def pipeline_overdue(db: Session = Depends(get_db)) -> list[OpportunitySummary]:
    return pipeline_service.list_overdue_summaries(db)


@router.get(
    "/opportunities/pipeline/stale", response_model=list[OpportunitySummary]
)
def pipeline_stale(
    threshold_days: int = Query(21, ge=1, le=365),
    db: Session = Depends(get_db),
) -> list[OpportunitySummary]:
    return pipeline_service.list_stale_summaries(db, threshold_days=threshold_days)


@router.get(
    "/opportunities/{opportunity_id}/timeline", response_model=TimelineResponse
)
def opportunity_timeline(
    opportunity_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> TimelineResponse:
    return timeline_service.build_opportunity_timeline(
        db, opportunity_id, limit=limit
    )


@router.post(
    "/opportunities/{opportunity_id}/follow-up-draft",
    response_model=FollowUpDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_follow_up_draft(
    opportunity_id: int,
    payload: FollowUpDraftRequest,
    db: Session = Depends(get_db),
) -> FollowUpDraftResponse:
    comm, run = communications_service.create_follow_up_draft(
        db, opportunity_id, payload
    )
    return FollowUpDraftResponse(communication=comm, workflow_run=run)


@router.get(
    "/opportunities/{opportunity_id}", response_model=InvestorOpportunityRead
)
def get_opportunity(
    opportunity_id: int, db: Session = Depends(get_db)
) -> InvestorOpportunityRead:
    return investor_service.get_opportunity(db, opportunity_id)


@router.patch(
    "/opportunities/{opportunity_id}", response_model=InvestorOpportunityRead
)
def update_opportunity(
    opportunity_id: int,
    payload: InvestorOpportunityUpdate,
    db: Session = Depends(get_db),
) -> InvestorOpportunityRead:
    return investor_service.update_opportunity(db, opportunity_id, payload)


@router.delete(
    "/opportunities/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_opportunity(
    opportunity_id: int, db: Session = Depends(get_db)
) -> Response:
    investor_service.delete_opportunity(db, opportunity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
