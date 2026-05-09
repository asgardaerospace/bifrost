"""Unified operational timeline HTTP routes — Sprint 7."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.operational_timeline import OperationalTimelineView
from app.services import operational_timeline as timeline_service

router = APIRouter()


@router.get("/operational-timeline", response_model=OperationalTimelineView)
def get_operational_timeline(
    mission_id: Optional[int] = Query(None),
    hours: int = Query(24, ge=1, le=336),
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> OperationalTimelineView:
    return timeline_service.build_timeline(
        db, mission_id=mission_id, hours=hours, limit=limit
    )


@router.get(
    "/missions/{mission_id}/operational-timeline",
    response_model=OperationalTimelineView,
)
def get_mission_operational_timeline(
    mission_id: int,
    hours: int = Query(72, ge=1, le=336),
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> OperationalTimelineView:
    return timeline_service.build_timeline(
        db, mission_id=mission_id, hours=hours, limit=limit
    )
