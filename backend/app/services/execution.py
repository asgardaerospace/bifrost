"""ExecutionService — queue projection + direct queue items.

Doctrine: /execution/queue projects existing tasks, approvals, pending drafts,
and overdue investor opportunities into queue items at read time. Persisted
items in `execution_queue_items` (recommendations, agent-proposed actions)
merge into the same view.

No double-write — projected items keep their source_type/source_id pointer and
have `is_projected=True`. Mutations (PATCH /execution/actions/:id) only apply
to persisted rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.communication import Communication
from app.models.execution_queue import ExecutionQueueItem
from app.models.investor import InvestorOpportunity
from app.models.market import MarketOpportunity
from app.models.task import Task
from app.schemas.execution import (
    ExecutionQueue,
    ExecutionQueueItemCreate,
    ExecutionQueueItemRead,
    ExecutionQueueItemUpdate,
)
from app.schemas.operational_event import OperationalEventCreate
from app.services import events as events_service
from app.services import governance as governance_service
from app.services import memory as memory_service
from app.services import pressure as pressure_service


# -- direct queue (persisted) ---------------------------------------------------


def _row_to_read(row: ExecutionQueueItem) -> ExecutionQueueItemRead:
    return ExecutionQueueItemRead(
        id=row.id,
        item_type=row.item_type,
        source_type=row.source_type,
        source_id=row.source_id,
        mission_id=row.mission_id,
        title=row.title,
        summary=row.summary,
        status=row.status,
        priority_score=row.priority_score,
        pressure_score=row.pressure_score,
        owner=row.owner,
        due_at=row.due_at,
        blocked_reason=row.blocked_reason,
        completed_at=row.completed_at,
        created_at=row.created_at,
        is_projected=False,
        requires_approval=row.requires_approval,
        meta=row.meta,
    )


# Sprint 1 — improved priority scoring. Combines base priority_score with
# due-date proximity and mission pressure. Cap [0,100].
def _scored_priority(row: ExecutionQueueItem | None, *, base: int, due_at, pressure: int = 0) -> int:
    score = max(0, min(100, base))
    if due_at is not None:
        delta = (due_at - datetime.now(timezone.utc)).total_seconds()
        if delta <= 0:
            score += 20  # overdue
        elif delta < 60 * 60 * 24:
            score += 12  # within 24h
        elif delta < 60 * 60 * 24 * 3:
            score += 6  # within 3 days
    if pressure:
        score += min(15, pressure // 7)
    return max(0, min(100, score))


def list_persisted(
    db: Session,
    *,
    mission_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[ExecutionQueueItem]:
    stmt = select(ExecutionQueueItem).where(
        ExecutionQueueItem.deleted_at.is_(None)
    )
    if mission_id is not None:
        stmt = stmt.where(ExecutionQueueItem.mission_id == mission_id)
    if status:
        stmt = stmt.where(ExecutionQueueItem.status == status)
    return list(db.scalars(stmt).all())


def create_item(
    db: Session,
    payload: ExecutionQueueItemCreate,
    *,
    actor: str = "system",
    requires_approval: bool = False,
) -> ExecutionQueueItem:
    data = payload.model_dump()
    # Service kwarg overrides whatever the schema carried; both paths must
    # converge on a single boolean.
    data["requires_approval"] = requires_approval or data.get("requires_approval", False)
    requires_approval = data["requires_approval"]
    item = ExecutionQueueItem(**data)
    db.add(item)
    db.flush()

    # If gated by approval, request the approval row inside the same transaction.
    if requires_approval:
        governance_service.request_queue_item_approval(
            db, item, requested_by=actor
        )

    event = events_service.publish(
        db,
        OperationalEventCreate(
            topic="execution",
            event_type="queue.item_created",
            mission_id=item.mission_id,
            entity_type="execution_queue_item",
            entity_id=item.id,
            actor=actor,
            payload={
                "item_type": item.item_type,
                "title": item.title,
                "priority_score": item.priority_score,
                "requires_approval": requires_approval,
            },
        ),
    )
    pressure_service.recompute_for_mission(
        db, item.mission_id, source="trigger", trigger_event_id=event.id
    )
    try:
        memory_service.ingest_queue_item(db, item)
    except Exception:
        pass
    db.commit()
    db.refresh(item)
    return item


def update_item(
    db: Session,
    item_id: int,
    payload: ExecutionQueueItemUpdate,
    *,
    actor: str = "system",
) -> ExecutionQueueItem:
    item = db.get(ExecutionQueueItem, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(
            status_code=404, detail=f"Queue item #{item_id} not found"
        )
    data = payload.model_dump(exclude_unset=True)
    new_status = data.get("status")
    prev_status = item.status

    # Governance gate: a requires_approval item can only transition to
    # 'completed' once an approved Approval row exists for it.
    if new_status == "completed" and item.requires_approval:
        if not governance_service.is_authorized_to_complete_queue_item(db, item):
            raise HTTPException(
                status_code=409,
                detail=(
                    "queue item requires approval before it can be completed; "
                    "request approval via /execution/actions/{id}/request-approval"
                ),
            )
        data.setdefault(
            "completed_at", datetime.now(timezone.utc)
        )

    for key, value in data.items():
        setattr(item, key, value)
    db.flush()

    if new_status and new_status != prev_status:
        event = events_service.publish(
            db,
            OperationalEventCreate(
                topic="execution",
                event_type=(
                    "queue.item_completed"
                    if new_status == "completed"
                    else "queue.item_status_changed"
                ),
                mission_id=item.mission_id,
                entity_type="execution_queue_item",
                entity_id=item.id,
                actor=actor,
                payload={
                    "from": prev_status,
                    "to": new_status,
                    "item_type": item.item_type,
                },
            ),
        )
        pressure_service.recompute_for_mission(
            db, item.mission_id, source="trigger", trigger_event_id=event.id
        )
        try:
            memory_service.ingest_queue_item(db, item)
        except Exception:
            pass

    db.commit()
    db.refresh(item)
    return item


def request_approval(
    db: Session, item_id: int, *, actor: str = "system", note: str | None = None
):
    """Open a pending Approval row for a queue item that requires one.

    Idempotent — returns the existing pending approval if one is open.
    """
    item = db.get(ExecutionQueueItem, item_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Queue item #{item_id} not found")
    if not item.requires_approval:
        raise HTTPException(
            status_code=409,
            detail="queue item does not require approval",
        )
    approval = governance_service.request_queue_item_approval(
        db, item, requested_by=actor, note=note
    )
    db.commit()
    db.refresh(approval)
    return approval


# -- projection (read-time adapters) -------------------------------------------


def _project_task(t: Task) -> ExecutionQueueItemRead:
    status = "blocked" if t.status == "blocked" else (
        "completed"
        if t.completed_at is not None
        else "in_progress"
        if t.status == "in_progress"
        else "queued"
    )
    return ExecutionQueueItemRead(
        id=None,
        item_type="task",
        source_type="task",
        source_id=t.id,
        mission_id=t.mission_id,
        title=t.title,
        summary=t.description,
        status=status,
        priority_score=({"high": 80, "medium": 50, "low": 20}.get(t.priority or "", 30)),
        owner=t.assignee,
        due_at=t.due_at,
        completed_at=t.completed_at,
        created_at=t.created_at,
        is_projected=True,
        meta={"task_status": t.status, "task_priority": t.priority},
    )


def _project_approval(a: Approval) -> ExecutionQueueItemRead:
    return ExecutionQueueItemRead(
        id=None,
        item_type="approval",
        source_type="approval",
        source_id=a.id,
        mission_id=a.mission_id,
        title=f"Approval: {a.action}",
        summary=a.decision_note,
        status="queued" if a.status == "pending" else "completed",
        priority_score=70,
        owner=a.reviewer,
        due_at=None,
        created_at=a.created_at,
        is_projected=True,
        meta={"approval_status": a.status, "requested_by": a.requested_by},
    )


def _project_draft(c: Communication) -> ExecutionQueueItemRead:
    return ExecutionQueueItemRead(
        id=None,
        item_type="draft",
        source_type="communication",
        source_id=c.id,
        mission_id=c.mission_id,
        title=f"Draft: {(c.subject or c.channel)[:120]}",
        summary=c.body[:200] + "…" if c.body and len(c.body) > 200 else c.body,
        status="queued" if c.status == "draft" else "in_progress",
        priority_score=55,
        owner=c.from_address,
        due_at=None,
        created_at=c.created_at,
        is_projected=True,
        meta={"channel": c.channel, "direction": c.direction, "status": c.status},
    )


def _project_inv_opp(o: InvestorOpportunity) -> ExecutionQueueItemRead:
    return ExecutionQueueItemRead(
        id=None,
        item_type="followup",
        source_type="investor_opportunity",
        source_id=o.id,
        mission_id=o.mission_id,
        title=f"Follow-up: opportunity #{o.id} ({o.stage})",
        summary=o.next_step,
        status="queued",
        priority_score=60,
        owner=o.owner,
        due_at=o.next_step_due_at,
        created_at=o.created_at,
        is_projected=True,
        meta={
            "stage": o.stage,
            "fit_score": o.fit_score,
            "probability_score": o.probability_score,
        },
    )


def _project_market_opp(o: MarketOpportunity) -> ExecutionQueueItemRead:
    return ExecutionQueueItemRead(
        id=None,
        item_type="followup",
        source_type="market_opportunity",
        source_id=o.id,
        mission_id=o.mission_id,
        title=f"Market follow-up: {o.name[:120]}",
        summary=o.next_step,
        status="queued",
        priority_score=50,
        due_at=o.next_step_due_at,
        created_at=o.created_at,
        is_projected=True,
        meta={"stage": o.stage},
    )


def build_queue(
    db: Session,
    *,
    mission_id: Optional[int] = None,
    status: Optional[str] = None,
    item_types: Optional[list[str]] = None,
    domains: Optional[list[str]] = None,
    min_priority: Optional[int] = None,
    requires_approval: Optional[bool] = None,
    limit: int = 200,
) -> ExecutionQueue:
    items: list[ExecutionQueueItemRead] = []

    types = set(item_types) if item_types else None
    domain_filter = set(domains) if domains else None
    now = datetime.now(timezone.utc)

    if types is None or "task" in types:
        stmt = select(Task).where(
            Task.deleted_at.is_(None), Task.completed_at.is_(None)
        )
        if mission_id is not None:
            stmt = stmt.where(Task.mission_id == mission_id)
        for t in db.scalars(stmt).all():
            items.append(_project_task(t))

    if types is None or "approval" in types:
        stmt = select(Approval).where(Approval.status == "pending")
        if mission_id is not None:
            stmt = stmt.where(Approval.mission_id == mission_id)
        for a in db.scalars(stmt).all():
            items.append(_project_approval(a))

    if types is None or "draft" in types:
        stmt = select(Communication).where(
            Communication.deleted_at.is_(None),
            Communication.status.in_(("draft", "pending_approval")),
        )
        if mission_id is not None:
            stmt = stmt.where(Communication.mission_id == mission_id)
        for c in db.scalars(stmt).all():
            items.append(_project_draft(c))

    if types is None or "followup" in types:
        stmt = select(InvestorOpportunity).where(
            InvestorOpportunity.deleted_at.is_(None),
            InvestorOpportunity.next_step_due_at.is_not(None),
            InvestorOpportunity.next_step_due_at <= now,
        )
        if mission_id is not None:
            stmt = stmt.where(InvestorOpportunity.mission_id == mission_id)
        for o in db.scalars(stmt).all():
            items.append(_project_inv_opp(o))

        stmt2 = select(MarketOpportunity).where(
            MarketOpportunity.deleted_at.is_(None),
            MarketOpportunity.next_step_due_at.is_not(None),
            MarketOpportunity.next_step_due_at <= now,
        )
        if mission_id is not None:
            stmt2 = stmt2.where(MarketOpportunity.mission_id == mission_id)
        for o2 in db.scalars(stmt2).all():
            items.append(_project_market_opp(o2))

    # Persisted items (recommendations, mission_action, etc.).
    persisted = list_persisted(db, mission_id=mission_id, status=status)
    for row in persisted:
        if types and row.item_type not in types:
            continue
        items.append(_row_to_read(row))

    if status:
        items = [i for i in items if i.status == status]
    if domain_filter:
        items = [i for i in items if (i.source_type or "") in domain_filter]
    if requires_approval is not None:
        items = [i for i in items if i.requires_approval is requires_approval]

    # Sprint 1 — boost priority by due-date proximity + mission pressure.
    for it in items:
        it.priority_score = _scored_priority(
            None,
            base=it.priority_score or 0,
            due_at=it.due_at,
            pressure=it.pressure_score or 0,
        )

    if min_priority is not None:
        items = [i for i in items if (i.priority_score or 0) >= min_priority]

    # Highest priority first, then earliest due, then most recent.
    items.sort(
        key=lambda i: (
            -(i.priority_score or 0),
            i.due_at or datetime.max.replace(tzinfo=timezone.utc),
            -(int(i.created_at.timestamp()) if i.created_at else 0),
        )
    )
    items = items[:limit]
    return ExecutionQueue(count=len(items), items=items)


def list_blockers(
    db: Session, *, mission_id: Optional[int] = None
) -> ExecutionQueue:
    """Surface anything blocked: tasks status='blocked' + persisted blocker items."""
    items: list[ExecutionQueueItemRead] = []

    stmt = select(Task).where(
        Task.deleted_at.is_(None),
        Task.status == "blocked",
    )
    if mission_id is not None:
        stmt = stmt.where(Task.mission_id == mission_id)
    for t in db.scalars(stmt).all():
        items.append(_project_task(t))

    stmt2 = select(ExecutionQueueItem).where(
        ExecutionQueueItem.deleted_at.is_(None),
        ExecutionQueueItem.status == "blocked",
    )
    if mission_id is not None:
        stmt2 = stmt2.where(ExecutionQueueItem.mission_id == mission_id)
    for row in db.scalars(stmt2).all():
        items.append(_row_to_read(row))

    return ExecutionQueue(count=len(items), items=items)


def list_pending_approvals(
    db: Session, *, mission_id: Optional[int] = None
) -> ExecutionQueue:
    stmt = select(Approval).where(Approval.status == "pending")
    if mission_id is not None:
        stmt = stmt.where(Approval.mission_id == mission_id)
    items = [_project_approval(a) for a in db.scalars(stmt).all()]
    return ExecutionQueue(count=len(items), items=items)
