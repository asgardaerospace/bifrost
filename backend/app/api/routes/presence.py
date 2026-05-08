"""Presence HTTP routes — non-realtime read surface."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.presence import PresenceList, PresenceSessionRead
from app.services import presence as presence_service

router = APIRouter()


@router.get("/presence/active", response_model=PresenceList)
def list_active(
    mission_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> PresenceList:
    presence_service.prune_stale(db)
    rows = presence_service.list_active(db, mission_id=mission_id)
    return PresenceList(
        count=len(rows),
        operators=[PresenceSessionRead.model_validate(r) for r in rows],
    )


@router.get(
    "/presence/mission/{mission_id}",
    response_model=PresenceList,
)
def list_for_mission(
    mission_id: int, db: Session = Depends(get_db)
) -> PresenceList:
    presence_service.prune_stale(db)
    rows = presence_service.list_active(db, mission_id=mission_id)
    return PresenceList(
        count=len(rows),
        operators=[PresenceSessionRead.model_validate(r) for r in rows],
    )
