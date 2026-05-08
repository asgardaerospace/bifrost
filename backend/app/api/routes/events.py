"""Operational events HTTP routes — long-poll stream + publish."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.operational_event import (
    OperationalEventCreate,
    OperationalEventRead,
    OperationalEventStream,
)
from app.services import events as events_service

router = APIRouter()


@router.get("/events", response_model=OperationalEventStream)
def stream_events(
    since: Optional[int] = Query(None, description="Last event id seen"),
    topic: Optional[str] = Query(None),
    topics: Optional[list[str]] = Query(
        None,
        description=(
            "Repeat to filter on multiple topics simultaneously. Overrides "
            "single-topic param when provided."
        ),
    ),
    mission_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> OperationalEventStream:
    return events_service.stream(
        db,
        since_id=since,
        topic=topic,
        topics=topics,
        mission_id=mission_id,
        severity=severity,
        limit=limit,
    )


@router.get("/events/replay", response_model=OperationalEventStream)
def replay_events(
    since: int = Query(..., description="Cursor — replay events with id > since"),
    topic: Optional[str] = Query(None),
    topics: Optional[list[str]] = Query(None),
    mission_id: Optional[int] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> OperationalEventStream:
    """Reconnect-safe replay: clients pass back the cursor returned in the
    last stream() response and receive everything since."""
    return events_service.stream(
        db,
        since_id=since,
        topic=topic,
        topics=topics,
        mission_id=mission_id,
        limit=limit,
    )


@router.post(
    "/events",
    response_model=OperationalEventRead,
    status_code=status.HTTP_201_CREATED,
)
def publish_event(
    payload: OperationalEventCreate, db: Session = Depends(get_db)
) -> OperationalEventRead:
    event = events_service.publish(db, payload)
    db.commit()
    db.refresh(event)
    return OperationalEventRead(
        id=event.id,
        topic=event.topic,
        event_type=event.event_type,
        mission_id=event.mission_id,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        actor=event.actor,
        source=event.source,
        severity=event.severity,
        payload=event.payload,
        created_at=event.created_at,
    )
