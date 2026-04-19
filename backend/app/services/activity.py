from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.activity import ActivityEvent

ACTOR_TYPE_USER = "user"


def log_activity(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    event_type: str,
    summary: str,
    actor: Optional[str] = None,
    actor_type: str = ACTOR_TYPE_USER,
    details: Optional[dict[str, Any]] = None,
) -> ActivityEvent:
    payload: dict[str, Any] = {"summary": summary}
    if details:
        payload["details"] = details

    event = ActivityEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        actor=actor,
        source=actor_type,
        payload=payload,
    )
    db.add(event)
    db.flush()
    return event
