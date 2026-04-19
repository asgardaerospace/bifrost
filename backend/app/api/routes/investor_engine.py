"""HTTP endpoints exposing investor-engine-sourced data inside Bifrost."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.integrations.investor_engine import drafts as engine_drafts
from app.integrations.investor_engine import service, sync
from app.integrations.investor_engine.mapper import NormalizedInvestor
from app.schemas.workflows import FollowUpDraftResponse

router = APIRouter()


@router.get("/investors", response_model=list[NormalizedInvestor])
def list_engine_investors(
    stage: Optional[str] = None,
    follow_up_status: Optional[str] = None,
    owner: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[NormalizedInvestor]:
    return service.list_investors(
        db,
        stage=stage,
        follow_up_status=follow_up_status,
        owner=owner,
        skip=skip,
        limit=limit,
    )


@router.get("/investors/{external_id}", response_model=NormalizedInvestor)
def get_engine_investor(
    external_id: str, db: Session = Depends(get_db)
) -> NormalizedInvestor:
    result = service.get_investor(db, external_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No engine investor with external_id={external_id!r}",
        )
    return result


@router.get("/follow-ups/due", response_model=list[NormalizedInvestor])
def due_follow_ups(
    as_of: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[NormalizedInvestor]:
    return service.follow_ups_due(db, as_of=as_of, limit=limit)


@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict[str, int]:
    return service.dashboard_summary(db)


@router.post(
    "/investors/{external_id}/follow-up-draft",
    response_model=FollowUpDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_engine_follow_up_draft(
    external_id: str,
    payload: engine_drafts.EngineFollowUpDraftRequest,
    db: Session = Depends(get_db),
) -> FollowUpDraftResponse:
    """Create a Bifrost follow-up draft anchored to an engine record.

    The draft lives entirely inside Bifrost. No write happens against
    the investor engine.
    """
    comm, run = engine_drafts.create_engine_follow_up_draft(
        db, external_id, payload
    )
    return FollowUpDraftResponse(communication=comm, workflow_run=run)


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
def trigger_sync(db: Session = Depends(get_db)) -> dict[str, int]:
    """Manually trigger a read-only pull from the investor engine."""
    report = sync.run_sync(db)
    return report.as_dict()
