from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.activity import ActivityEvent
from app.schemas.activity import ActivityEventRead

router = APIRouter()


@router.get("/", response_model=list[ActivityEventRead])
def list_activity_events(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    event_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ActivityEventRead]:
    stmt = select(ActivityEvent)
    if entity_type is not None:
        stmt = stmt.where(ActivityEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(ActivityEvent.entity_id == entity_id)
    if event_type is not None:
        stmt = stmt.where(ActivityEvent.event_type == event_type)
    stmt = stmt.order_by(desc(ActivityEvent.created_at)).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())
