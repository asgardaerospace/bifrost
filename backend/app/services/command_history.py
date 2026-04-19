"""Command history uses the existing ActivityEvent table.

No new table: event_type='command.executed', source='command_console'.
entity_type/entity_id track the referenced entity when resolved, else
('command', 0) as a free-floating marker. Full command details live in
payload.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.activity import ActivityEvent
from app.schemas.command_console import (
    CommandClassification,
    CommandHistoryItem,
    CommandResponse,
    EntityRef,
)

COMMAND_EVENT_TYPE = "command.executed"
COMMAND_SOURCE = "command_console"
COMMAND_ENTITY_PLACEHOLDER = "command"


def _referenced(classification: CommandClassification) -> tuple[str, int]:
    ref = classification.referenced_entity
    if ref is not None:
        return ref.entity_type, ref.entity_id
    return COMMAND_ENTITY_PLACEHOLDER, 0


def record_command(
    db: Session,
    *,
    actor: Optional[str],
    command_text: str,
    normalized_text: str,
    classification: CommandClassification,
    output_type: str,
    status: str,
    duration_ms: int,
    records_created: list[EntityRef],
) -> ActivityEvent:
    entity_type, entity_id = _referenced(classification)

    payload: dict[str, Any] = {
        "summary": f"Command executed: {classification.intent} ({status})",
        "command": {
            "text": command_text,
            "normalized_text": normalized_text,
        },
        "classification": classification.model_dump(),
        "output_type": output_type,
        "status": status,
        "duration_ms": duration_ms,
        "records_created": [r.model_dump() for r in records_created],
    }

    event = ActivityEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=COMMAND_EVENT_TYPE,
        actor=actor,
        source=COMMAND_SOURCE,
        payload=payload,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_history(
    db: Session, *, skip: int = 0, limit: int = 50
) -> list[CommandHistoryItem]:
    stmt = (
        select(ActivityEvent)
        .where(ActivityEvent.event_type == COMMAND_EVENT_TYPE)
        .order_by(desc(ActivityEvent.created_at))
        .offset(skip)
        .limit(limit)
    )
    rows = db.scalars(stmt).all()
    items: list[CommandHistoryItem] = []
    for e in rows:
        payload: dict[str, Any] = e.payload or {}
        classification = payload.get("classification") or {}
        command = payload.get("command") or {}
        ref = classification.get("referenced_entity") or {}
        items.append(
            CommandHistoryItem(
                id=e.id,
                command_text=command.get("text", ""),
                normalized_text=command.get("normalized_text"),
                command_class=classification.get("command_class"),
                referenced_entity_type=ref.get("entity_type"),
                referenced_entity_id=ref.get("entity_id"),
                output_type=payload.get("output_type"),
                records_created=bool(payload.get("records_created")),
                status=payload.get("status"),
                duration_ms=payload.get("duration_ms"),
                actor=e.actor,
                created_at=e.created_at,
            )
        )
    return items
