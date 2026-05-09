"""Executive Horizon HTTP routes — Sprint 7."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.horizon import HorizonView
from app.services import horizon as horizon_service

router = APIRouter()


@router.get("/horizon", response_model=HorizonView)
def get_horizon(
    top_n: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
) -> HorizonView:
    return horizon_service.build_horizon(db, top_n=top_n)
