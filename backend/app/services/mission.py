"""MissionService — canonical mission lifecycle, pressure, dependencies, timeline.

Sprint 0 scaffold. Real pressure model + propagation arrives in Sprint 2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.activity import ActivityEvent
from app.models.approval import Approval
from app.models.communication import Communication
from app.models.intel import IntelItem
from app.models.investor import InvestorOpportunity
from app.models.market import MarketOpportunity
from app.models.mission import Mission, MissionEntity
from app.models.note import Note
from app.models.program import Program
from app.models.relationship import Relationship
from app.models.task import Task
from app.schemas.operational_event import OperationalEventCreate
from app.services import events as events_service
from app.services import memory as memory_service
from app.services import pressure as pressure_service
from app.schemas.mission import (
    MissionCreate,
    MissionDependencies,
    MissionDependencyEdge,
    MissionEntityCreate,
    MissionPressure,
    MissionTimeline,
    MissionTimelineItem,
    MissionUpdate,
)


# Mission-level relationship types we project as upstream/downstream dependency.
_MISSION_DEP_TYPES = ("depends_on", "blocks", "supports", "escalates_to", "mitigates")


# -- lifecycle ------------------------------------------------------------------


def list_missions(
    db: Session,
    *,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    owner_user_id: Optional[int] = None,
    include_deleted: bool = False,
) -> list[Mission]:
    stmt = select(Mission)
    if not include_deleted:
        stmt = stmt.where(Mission.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Mission.status == status)
    if priority:
        stmt = stmt.where(Mission.priority == priority)
    if owner_user_id is not None:
        stmt = stmt.where(Mission.owner_user_id == owner_user_id)
    stmt = stmt.order_by(Mission.priority.desc(), Mission.created_at.desc())
    return list(db.scalars(stmt).all())


def get_mission(db: Session, mission_id: int) -> Mission:
    mission = db.get(Mission, mission_id)
    if mission is None or mission.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Mission #{mission_id} not found")
    return mission


def get_mission_by_codename(db: Session, codename: str) -> Mission:
    stmt = (
        select(Mission)
        .where(Mission.codename == codename)
        .where(Mission.deleted_at.is_(None))
    )
    mission = db.scalars(stmt).first()
    if mission is None:
        raise HTTPException(
            status_code=404, detail=f"Mission '{codename}' not found"
        )
    return mission


def create_mission(
    db: Session, payload: MissionCreate, *, actor: str = "system"
) -> Mission:
    existing = db.scalars(
        select(Mission).where(Mission.codename == payload.codename)
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Mission codename '{payload.codename}' already exists",
        )
    mission = Mission(**payload.model_dump())
    db.add(mission)
    db.flush()
    event = events_service.publish(
        db,
        OperationalEventCreate(
            topic="missions",
            event_type="mission.created",
            mission_id=mission.id,
            entity_type="mission",
            entity_id=mission.id,
            actor=actor,
            payload={
                "codename": mission.codename,
                "name": mission.name,
                "priority": mission.priority,
                "status": mission.status,
            },
        ),
    )
    pressure_service.recompute_for_mission(
        db, mission.id, source="trigger", trigger_event_id=event.id
    )
    try:
        memory_service.ingest_mission(db, mission)
    except Exception:
        # Memory ingestion is best-effort; an embedding-provider failure must
        # not block mission creation. The record stays in embedding_status='pending'
        # and can be refreshed via /memory/records/{id}/refresh.
        pass
    db.commit()
    db.refresh(mission)
    return mission


def update_mission(
    db: Session,
    mission_id: int,
    payload: MissionUpdate,
    *,
    actor: str = "system",
) -> Mission:
    mission = get_mission(db, mission_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return mission
    for key, value in data.items():
        setattr(mission, key, value)
    db.flush()
    event = events_service.publish(
        db,
        OperationalEventCreate(
            topic="missions",
            event_type="mission.updated",
            mission_id=mission.id,
            entity_type="mission",
            entity_id=mission.id,
            actor=actor,
            payload={"changed": list(data.keys())},
        ),
    )
    pressure_service.recompute_for_mission(
        db, mission.id, source="trigger", trigger_event_id=event.id
    )
    try:
        memory_service.ingest_mission(db, mission)
    except Exception:
        pass
    db.commit()
    db.refresh(mission)
    return mission


def soft_delete_mission(
    db: Session, mission_id: int, *, actor: str = "system"
) -> None:
    mission = get_mission(db, mission_id)
    mission.deleted_at = datetime.now(timezone.utc)
    db.flush()
    events_service.publish(
        db,
        OperationalEventCreate(
            topic="missions",
            event_type="mission.deleted",
            mission_id=mission.id,
            entity_type="mission",
            entity_id=mission.id,
            actor=actor,
            severity="warning",
        ),
    )
    try:
        memory_service.soft_delete_for_source(
            db, source_type="mission", source_id=mission.id
        )
    except Exception:
        pass
    db.commit()


# -- mission entities -----------------------------------------------------------


def list_entities(db: Session, mission_id: int) -> list[MissionEntity]:
    get_mission(db, mission_id)
    stmt = (
        select(MissionEntity)
        .where(MissionEntity.mission_id == mission_id)
        .order_by(MissionEntity.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def link_entity(
    db: Session,
    mission_id: int,
    payload: MissionEntityCreate,
    *,
    actor: str = "system",
) -> MissionEntity:
    get_mission(db, mission_id)
    existing = db.scalars(
        select(MissionEntity).where(
            MissionEntity.mission_id == mission_id,
            MissionEntity.entity_type == payload.entity_type,
            MissionEntity.entity_id == payload.entity_id,
            MissionEntity.relationship_type == payload.relationship_type,
        )
    ).first()
    if existing is not None:
        return existing
    link = MissionEntity(mission_id=mission_id, **payload.model_dump())
    db.add(link)
    db.flush()
    event = events_service.publish(
        db,
        OperationalEventCreate(
            topic="missions",
            event_type="mission.entity_linked",
            mission_id=mission_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            actor=actor,
            payload={
                "link_id": link.id,
                "relationship_type": payload.relationship_type,
            },
        ),
    )
    pressure_service.recompute_for_mission(
        db, mission_id, source="trigger", trigger_event_id=event.id
    )
    db.commit()
    db.refresh(link)
    return link


def unlink_entity(
    db: Session, mission_id: int, link_id: int, *, actor: str = "system"
) -> None:
    link = db.get(MissionEntity, link_id)
    if link is None or link.mission_id != mission_id:
        raise HTTPException(status_code=404, detail="Mission link not found")
    entity_type = link.entity_type
    entity_id = link.entity_id
    db.delete(link)
    db.flush()
    events_service.publish(
        db,
        OperationalEventCreate(
            topic="missions",
            event_type="mission.entity_unlinked",
            mission_id=mission_id,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            payload={"link_id": link_id},
        ),
    )
    db.commit()


def list_linked_entities_grouped(
    db: Session, mission_id: int
) -> dict[str, list[MissionEntity]]:
    """Mission entities grouped by entity_type — for the mission detail tabs."""
    rows = list_entities(db, mission_id)
    grouped: dict[str, list[MissionEntity]] = {}
    for row in rows:
        grouped.setdefault(row.entity_type, []).append(row)
    return grouped


# -- pressure (Sprint 0 scaffold) ----------------------------------------------


def build_pressure(db: Session, mission_id: int) -> MissionPressure:
    """Pressure read-side surface — Sprint 2.

    Returns a fresh computation (always live), which also persists a snapshot
    so /missions/{id}/pressure/history accumulates a trajectory over time.
    Caller is responsible for committing.
    """
    snapshot = pressure_service.compute_pressure(
        db, mission_id, persist=True, source="trigger"
    )
    db.commit()
    db.refresh(snapshot)
    return pressure_service.to_mission_pressure(snapshot)


def build_pressure_legacy(db: Session, mission_id: int) -> MissionPressure:
    """Sprint 0 scaffold — kept for reference / fallback. Not wired to a route."""
    mission = get_mission(db, mission_id)
    now = datetime.now(timezone.utc)

    # Blockers: tasks with status 'blocked' linked to this mission.
    blockers = db.scalars(
        select(Task).where(
            Task.mission_id == mission_id,
            Task.status == "blocked",
            Task.deleted_at.is_(None),
        )
    ).all()

    # Overdue: tasks past due_at, opps past next_step_due_at, all linked to mission.
    overdue_tasks = db.scalars(
        select(Task).where(
            Task.mission_id == mission_id,
            Task.due_at.is_not(None),
            Task.due_at < now,
            Task.completed_at.is_(None),
            Task.deleted_at.is_(None),
        )
    ).all()
    overdue_inv_opps = db.scalars(
        select(InvestorOpportunity).where(
            InvestorOpportunity.mission_id == mission_id,
            InvestorOpportunity.next_step_due_at.is_not(None),
            InvestorOpportunity.next_step_due_at < now,
            InvestorOpportunity.deleted_at.is_(None),
        )
    ).all()
    overdue_market_opps = db.scalars(
        select(MarketOpportunity).where(
            MarketOpportunity.mission_id == mission_id,
            MarketOpportunity.next_step_due_at.is_not(None),
            MarketOpportunity.next_step_due_at < now,
            MarketOpportunity.deleted_at.is_(None),
        )
    ).all()

    pending_approvals = db.scalars(
        select(Approval).where(
            Approval.mission_id == mission_id, Approval.status == "pending"
        )
    ).all()

    overdue_count = (
        len(overdue_tasks) + len(overdue_inv_opps) + len(overdue_market_opps)
    )

    base = mission.pressure_score or 0
    blockers_pts = min(40, len(blockers) * 10)
    overdue_pts = min(40, overdue_count * 5)
    approvals_pts = min(20, len(pending_approvals) * 3)
    derived = base + blockers_pts + overdue_pts + approvals_pts
    derived = max(0, min(100, derived))

    if derived >= 80:
        health = "critical"
    elif derived >= 60:
        health = "strain"
    elif derived >= 35:
        health = "watch"
    else:
        health = "nominal"

    return MissionPressure(
        mission_id=mission_id,
        pressure_score=derived,
        health_status=health,
        components={
            "base": base,
            "blockers": blockers_pts,
            "overdue": overdue_pts,
            "pending_approvals": approvals_pts,
        },
        blockers_count=len(blockers),
        overdue_count=overdue_count,
        pending_approvals_count=len(pending_approvals),
        explanation=(
            f"Pressure {derived}/100 derived from base={base}, "
            f"blockers={blockers_pts}, overdue={overdue_pts}, "
            f"approvals={approvals_pts}. Sprint 0 scaffold — real model in Sprint 2."
        ),
    )


# -- dependencies ---------------------------------------------------------------


def build_dependencies(db: Session, mission_id: int) -> MissionDependencies:
    mission = get_mission(db, mission_id)

    upstream: list[MissionDependencyEdge] = []
    downstream: list[MissionDependencyEdge] = []

    # Use the relationships table where mission ↔ mission edges are stored.
    stmt = select(Relationship).where(
        Relationship.deleted_at.is_(None),
        Relationship.relationship_type.in_(_MISSION_DEP_TYPES),
        or_(
            (Relationship.source_type == "mission")
            & (Relationship.source_id == mission_id),
            (Relationship.target_type == "mission")
            & (Relationship.target_id == mission_id),
        ),
    )
    edges = list(db.scalars(stmt).all())

    other_ids = {
        e.target_id if e.source_id == mission_id else e.source_id for e in edges
    }
    other_missions = {
        m.id: m
        for m in (
            db.scalars(
                select(Mission).where(Mission.id.in_(other_ids or {-1}))
            ).all()
        )
    }

    for edge in edges:
        if edge.source_type == "mission" and edge.source_id == mission_id:
            other = other_missions.get(edge.target_id)
            downstream.append(
                MissionDependencyEdge(
                    relationship_type=edge.relationship_type,
                    other_mission_id=edge.target_id,
                    other_codename=other.codename if other else None,
                    other_name=other.name if other else None,
                    direction="downstream",
                )
            )
        else:
            other = other_missions.get(edge.source_id)
            upstream.append(
                MissionDependencyEdge(
                    relationship_type=edge.relationship_type,
                    other_mission_id=edge.source_id,
                    other_codename=other.codename if other else None,
                    other_name=other.name if other else None,
                    direction="upstream",
                )
            )

    # Parent mission counts as upstream.
    if mission.parent_mission_id is not None:
        parent = db.get(Mission, mission.parent_mission_id)
        upstream.append(
            MissionDependencyEdge(
                relationship_type="participates_in",
                other_mission_id=mission.parent_mission_id,
                other_codename=parent.codename if parent else None,
                other_name=parent.name if parent else None,
                direction="upstream",
            )
        )

    return MissionDependencies(
        mission_id=mission_id, upstream=upstream, downstream=downstream
    )


# -- timeline -------------------------------------------------------------------


def build_timeline(
    db: Session, mission_id: int, *, limit: int = 200
) -> MissionTimeline:
    """Aggregate timeline across all entities linked to the mission.

    Reuses the same shape as services/timeline.py but pivots on mission_id +
    polymorphic mission_entities rather than a single opportunity.
    """
    get_mission(db, mission_id)
    items: list[MissionTimelineItem] = []

    # Direct mission_id links on tasks, communications, approvals, intel.
    for task in db.scalars(
        select(Task).where(
            Task.mission_id == mission_id, Task.deleted_at.is_(None)
        )
    ).all():
        items.append(
            MissionTimelineItem(
                item_type="task",
                item_id=task.id,
                occurred_at=task.completed_at or task.due_at or task.created_at,
                title=f"Task: {task.title}",
                summary=task.description,
                actor=task.assignee,
                entity_type="task",
                entity_id=task.id,
                data={
                    "status": task.status,
                    "priority": task.priority,
                },
            )
        )
    for comm in db.scalars(
        select(Communication).where(
            Communication.mission_id == mission_id,
            Communication.deleted_at.is_(None),
        )
    ).all():
        items.append(
            MissionTimelineItem(
                item_type="communication",
                item_id=comm.id,
                occurred_at=comm.sent_at or comm.created_at,
                title=f"{comm.channel} {comm.direction} — {comm.status}",
                summary=comm.subject,
                entity_type="communication",
                entity_id=comm.id,
            )
        )
    for appr in db.scalars(
        select(Approval).where(Approval.mission_id == mission_id)
    ).all():
        items.append(
            MissionTimelineItem(
                item_type="approval",
                item_id=appr.id,
                occurred_at=appr.reviewed_at or appr.created_at,
                title=f"Approval: {appr.action} ({appr.status})",
                actor=appr.reviewer or appr.requested_by,
                entity_type="approval",
                entity_id=appr.id,
            )
        )

    # Mission-linked notes via entity_type='mission'.
    for note in db.scalars(
        select(Note).where(
            Note.entity_type == "mission",
            Note.entity_id == mission_id,
            Note.deleted_at.is_(None),
        )
    ).all():
        body = note.body or ""
        items.append(
            MissionTimelineItem(
                item_type="note",
                item_id=note.id,
                occurred_at=note.created_at,
                title="Note",
                summary=body[:280] + ("…" if len(body) > 280 else ""),
                actor=note.author,
                entity_type="note",
                entity_id=note.id,
            )
        )

    # Activity events on the mission entity itself.
    for event in db.scalars(
        select(ActivityEvent).where(
            ActivityEvent.entity_type == "mission",
            ActivityEvent.entity_id == mission_id,
        )
    ).all():
        payload = event.payload or {}
        items.append(
            MissionTimelineItem(
                item_type="activity_event",
                item_id=event.id,
                occurred_at=event.created_at,
                title=event.event_type,
                summary=(
                    payload.get("summary") if isinstance(payload, dict) else None
                ),
                actor=event.actor,
                entity_type="mission",
                entity_id=mission_id,
                data={"source": event.source, "payload": payload},
            )
        )

    # Intel items linked to the mission. (IntelItem has no deleted_at — intel
    # is external provenance and always preserved.)
    for intel in db.scalars(
        select(IntelItem).where(IntelItem.mission_id == mission_id)
    ).all():
        items.append(
            MissionTimelineItem(
                item_type="intel",
                item_id=intel.id,
                occurred_at=intel.published_at or intel.created_at,
                title=f"Intel: {intel.title[:120]}",
                summary=intel.summary,
                entity_type="intel_item",
                entity_id=intel.id,
                data={
                    "source": intel.source,
                    "category": intel.category,
                    "strategic_relevance_score": intel.strategic_relevance_score,
                },
            )
        )

    items.sort(key=lambda i: i.occurred_at, reverse=True)
    items = items[:limit]
    return MissionTimeline(mission_id=mission_id, count=len(items), items=items)
