"""Operational event bus — persisted log + realtime pub/sub fanout.

Doctrine bus topics (canonical): missions, intelligence, execution, graph,
memory, agents, presence, approvals, events.

Sprint 2: persistence-then-broadcast. The publish path always writes the row
first (durable), then schedules a websocket fanout via the pubsub manager.
If the loop isn't running (smoke tests), broadcast is a silent no-op.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operational_event import OperationalEvent
from app.schemas.operational_event import (
    OperationalEventCreate,
    OperationalEventRead,
    OperationalEventStream,
)
from app.services import pubsub as pubsub_module


def publish(db: Session, payload: OperationalEventCreate) -> OperationalEvent:
    """Persist an operational event and schedule websocket fanout.

    Persistence first. If the same DB transaction rolls back later, the
    broadcast cannot be unsent — but the persisted record will also have
    been rolled back, so subscribers can reconcile via /events?since=cursor
    and discover the missing id.
    """
    event = OperationalEvent(**payload.model_dump())
    db.add(event)
    db.flush()

    # Schedule realtime fanout. Sync caller bridges into the loop; if no
    # loop is bound (test client without ws layer), this is a no-op.
    pubsub_module.manager.publish_sync(
        event.topic,
        event.mission_id,
        {
            "type": "event",
            "topic": event.topic,
            "event_type": event.event_type,
            "id": event.id,
            "mission_id": event.mission_id,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "actor": event.actor,
            "source": event.source,
            "severity": event.severity,
            "payload": event.payload,
            "occurred_at": event.created_at.isoformat() if event.created_at else None,
        },
    )
    return event


def stream(
    db: Session,
    *,
    since_id: Optional[int] = None,
    topic: Optional[str] = None,
    topics: Optional[list[str]] = None,
    mission_id: Optional[int] = None,
    severity: Optional[str] = None,
    limit: int = 100,
) -> OperationalEventStream:
    stmt = select(OperationalEvent)
    if since_id is not None:
        stmt = stmt.where(OperationalEvent.id > since_id)
    # Sprint 2 — accept multi-topic filter alongside the single-topic one.
    if topics:
        stmt = stmt.where(OperationalEvent.topic.in_(topics))
    elif topic:
        stmt = stmt.where(OperationalEvent.topic == topic)
    if mission_id is not None:
        stmt = stmt.where(OperationalEvent.mission_id == mission_id)
    if severity:
        stmt = stmt.where(OperationalEvent.severity == severity)
    stmt = stmt.order_by(OperationalEvent.id.asc()).limit(limit)
    rows = list(db.scalars(stmt).all())
    items = [
        OperationalEventRead(
            id=r.id,
            topic=r.topic,
            event_type=r.event_type,
            mission_id=r.mission_id,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            actor=r.actor,
            source=r.source,
            severity=r.severity,
            payload=r.payload,
            created_at=r.created_at,
        )
        for r in rows
    ]
    cursor = items[-1].id if items else since_id
    return OperationalEventStream(count=len(items), cursor=cursor, items=items)
