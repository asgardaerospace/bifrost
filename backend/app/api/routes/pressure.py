"""Pressure history endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.pressure import PressureHistory, PressureSnapshotRead
from app.services import pressure as pressure_service

router = APIRouter()


@router.get(
    "/missions/{mission_id}/pressure/history",
    response_model=PressureHistory,
)
def pressure_history(
    mission_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> PressureHistory:
    rows = pressure_service.list_history(db, mission_id, limit=limit)
    return PressureHistory(
        mission_id=mission_id,
        count=len(rows),
        snapshots=[PressureSnapshotRead.model_validate(r) for r in rows],
    )


@router.post(
    "/missions/{mission_id}/pressure/recompute",
    response_model=PressureSnapshotRead,
)
def recompute(mission_id: int, db: Session = Depends(get_db)) -> PressureSnapshotRead:
    snapshot = pressure_service.compute_pressure(
        db, mission_id, persist=True, source="manual"
    )
    db.commit()
    db.refresh(snapshot)
    return PressureSnapshotRead.model_validate(snapshot)
