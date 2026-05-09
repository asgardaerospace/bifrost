"""Mission topology HTTP routes — Sprint 7."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.topology import TopologyView
from app.services import topology as topology_service

router = APIRouter()


@router.get("/topology", response_model=TopologyView)
def get_topology(
    mission_id: Optional[int] = Query(None),
    include_intel: bool = Query(True),
    db: Session = Depends(get_db),
) -> TopologyView:
    return topology_service.build_topology(
        db, mission_id=mission_id, include_intel=include_intel
    )


@router.get("/missions/{mission_id}/topology", response_model=TopologyView)
def get_mission_topology(
    mission_id: int,
    include_intel: bool = Query(True),
    db: Session = Depends(get_db),
) -> TopologyView:
    return topology_service.build_topology(
        db, mission_id=mission_id, include_intel=include_intel
    )
