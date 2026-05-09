"""Environmental telemetry HTTP routes — Sprint 7."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.environment import EnvironmentSnapshot
from app.services import environment as environment_service

router = APIRouter()


@router.get("/environment", response_model=EnvironmentSnapshot)
def get_environment(db: Session = Depends(get_db)) -> EnvironmentSnapshot:
    return environment_service.build_snapshot(db)
