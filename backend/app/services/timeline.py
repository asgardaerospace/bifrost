from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity import ActivityEvent
from app.models.communication import Communication
from app.models.meeting import Meeting
from app.models.note import Note
from app.models.task import Task
from app.schemas.timeline import TimelineItem, TimelineResponse
from app.services.investor import get_opportunity

ENTITY_OPPORTUNITY = "investor_opportunity"


def _pick_timestamp(*candidates: Optional[datetime]) -> datetime:
    for c in candidates:
        if c is not None:
            return c
    return datetime.min.replace(tzinfo=timezone.utc)


def _activity_item(event: ActivityEvent) -> TimelineItem:
    payload: dict[str, Any] = event.payload or {}
    summary = payload.get("summary") if isinstance(payload, dict) else None
    return TimelineItem(
        item_type="activity_event",
        item_id=event.id,
        occurred_at=event.created_at,
        title=event.event_type,
        summary=summary,
        actor=event.actor,
        data={"source": event.source, "payload": payload},
    )


def _communication_item(c: Communication) -> TimelineItem:
    title = f"{c.channel} {c.direction} — {c.status}"
    return TimelineItem(
        item_type="communication",
        item_id=c.id,
        occurred_at=_pick_timestamp(c.sent_at, c.created_at),
        title=title,
        summary=c.subject,
        data={
            "channel": c.channel,
            "direction": c.direction,
            "status": c.status,
            "from_address": c.from_address,
            "to_address": c.to_address,
            "sent_at": c.sent_at.isoformat() if c.sent_at else None,
        },
    )


def _meeting_item(m: Meeting) -> TimelineItem:
    return TimelineItem(
        item_type="meeting",
        item_id=m.id,
        occurred_at=_pick_timestamp(m.starts_at, m.created_at),
        title=m.title,
        summary=m.outcome or m.next_step,
        data={
            "location": m.location,
            "starts_at": m.starts_at.isoformat() if m.starts_at else None,
            "ends_at": m.ends_at.isoformat() if m.ends_at else None,
            "next_step": m.next_step,
        },
    )


def _note_item(n: Note) -> TimelineItem:
    body = n.body or ""
    return TimelineItem(
        item_type="note",
        item_id=n.id,
        occurred_at=n.created_at,
        title="Note",
        summary=body[:280] + ("…" if len(body) > 280 else ""),
        actor=n.author,
    )


def _task_item(t: Task) -> TimelineItem:
    title = f"Task: {t.title}"
    return TimelineItem(
        item_type="task",
        item_id=t.id,
        occurred_at=_pick_timestamp(t.completed_at, t.due_at, t.created_at),
        title=title,
        summary=t.description,
        actor=t.assignee,
        data={
            "status": t.status,
            "priority": t.priority,
            "due_at": t.due_at.isoformat() if t.due_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        },
    )


def build_opportunity_timeline(
    db: Session,
    opportunity_id: int,
    *,
    limit: int = 200,
) -> TimelineResponse:
    # 404 if the opportunity is missing or soft-deleted.
    get_opportunity(db, opportunity_id)

    items: list[TimelineItem] = []

    events = db.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.entity_type == ENTITY_OPPORTUNITY)
        .where(ActivityEvent.entity_id == opportunity_id)
    ).all()
    items.extend(_activity_item(e) for e in events)

    comms = db.scalars(
        select(Communication)
        .where(Communication.entity_type == ENTITY_OPPORTUNITY)
        .where(Communication.entity_id == opportunity_id)
        .where(Communication.deleted_at.is_(None))
    ).all()
    items.extend(_communication_item(c) for c in comms)

    meetings = db.scalars(
        select(Meeting)
        .where(Meeting.entity_type == ENTITY_OPPORTUNITY)
        .where(Meeting.entity_id == opportunity_id)
        .where(Meeting.deleted_at.is_(None))
    ).all()
    items.extend(_meeting_item(m) for m in meetings)

    notes = db.scalars(
        select(Note)
        .where(Note.entity_type == ENTITY_OPPORTUNITY)
        .where(Note.entity_id == opportunity_id)
        .where(Note.deleted_at.is_(None))
    ).all()
    items.extend(_note_item(n) for n in notes)

    tasks = db.scalars(
        select(Task)
        .where(Task.entity_type == ENTITY_OPPORTUNITY)
        .where(Task.entity_id == opportunity_id)
        .where(Task.deleted_at.is_(None))
    ).all()
    items.extend(_task_item(t) for t in tasks)

    items.sort(key=lambda i: i.occurred_at, reverse=True)
    items = items[:limit]

    return TimelineResponse(
        investor_opportunity_id=opportunity_id,
        count=len(items),
        items=items,
    )
