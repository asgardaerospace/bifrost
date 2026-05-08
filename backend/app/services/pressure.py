"""Mission pressure engine — Sprint 2.

Replaces the Sprint 0 scaffold in services/mission.build_pressure with a
deterministic, weighted, persisted, replayable scoring model.

Inputs (all derivable from canonical operational state):
  • blockers — queue items in status='blocked' OR tasks status='blocked'
  • overdue — queue items / opportunities past their due_at, not completed
  • pending approvals — Approval rows in pending status, scoped to mission
  • unresolved dependencies — upstream missions in active/strain/critical
    health that we depend_on/blocks (via relationships)
  • high-priority intel — IntelItem with strategic_relevance_score >= 70
    and mission_id == this one
  • activity volume — operational_events in the last hour for this mission
    (saturation signal — high churn alone counts as pressure)
  • escalation flags — operational events of severity=critical|warning in
    the last 24h scoped to this mission

Output: deterministic 0..100 score + component breakdown + health band.
Scoring weights are module-level constants for inspection/tuning.

Each compute_pressure() call optionally persists a MissionPressureSnapshot
so /missions/{id}/pressure/history is meaningful.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.execution_queue import ExecutionQueueItem
from app.models.intel import IntelItem
from app.models.investor import InvestorOpportunity
from app.models.market import MarketOpportunity
from app.models.mission import Mission
from app.models.operational_event import OperationalEvent
from app.models.pressure_snapshot import MissionPressureSnapshot
from app.models.relationship import Relationship
from app.models.task import Task
from app.schemas.mission import MissionPressure
from app.services import signal_propagation as signal_propagation_service


# -- weights (each capped, total clipped to 100) -------------------------------

W_BLOCKERS_PER = 8
W_BLOCKERS_CAP = 30

W_OVERDUE_PER = 4
W_OVERDUE_CAP = 25

W_APPROVALS_PER = 3
W_APPROVALS_CAP = 15

W_UNRESOLVED_DEPS_PER = 6
W_UNRESOLVED_DEPS_CAP = 18

W_INTEL_PER = 5
W_INTEL_CAP = 15

W_ACTIVITY_VOLUME_THRESHOLD = 20  # events/hr above which we add pressure
W_ACTIVITY_PER_OVER_THRESHOLD = 1
W_ACTIVITY_CAP = 12

W_ESCALATION_PER = 7
W_ESCALATION_CAP = 20

# Sprint 4 — signed contribution from intelligence signal impacts. The
# aggregate is already capped at +/- 30 inside signal_propagation; we let
# the full signed value flow into the score so opportunities relieve and
# risks raise pressure. Operators audit via components["signal_impact"].
W_SIGNAL_IMPACT_CAP_POS = 30
W_SIGNAL_IMPACT_CAP_NEG = -20

W_BASE_FROM_PRIORITY = {"critical": 15, "high": 8, "normal": 0, "low": -5}

HEALTH_BANDS = (
    (80, "critical"),
    (60, "strain"),
    (35, "watch"),
    (0, "nominal"),
)


def _band(score: int) -> str:
    for threshold, label in HEALTH_BANDS:
        if score >= threshold:
            return label
    return "nominal"


def compute_pressure(
    db: Session,
    mission_id: int,
    *,
    persist: bool = True,
    source: str = "trigger",
    trigger_event_id: Optional[int] = None,
) -> MissionPressureSnapshot:
    mission = db.get(Mission, mission_id)
    if mission is None or mission.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Mission #{mission_id} not found")

    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(hours=24)

    # ---- counts -----------------------------------------------------------
    blockers_queue = db.scalars(
        select(ExecutionQueueItem)
        .where(ExecutionQueueItem.mission_id == mission_id)
        .where(ExecutionQueueItem.status == "blocked")
        .where(ExecutionQueueItem.deleted_at.is_(None))
    ).all()
    blockers_tasks = db.scalars(
        select(Task)
        .where(Task.mission_id == mission_id)
        .where(Task.status == "blocked")
        .where(Task.deleted_at.is_(None))
    ).all()
    blockers_count = len(blockers_queue) + len(blockers_tasks)

    overdue_queue = db.scalars(
        select(ExecutionQueueItem)
        .where(ExecutionQueueItem.mission_id == mission_id)
        .where(ExecutionQueueItem.due_at.is_not(None))
        .where(ExecutionQueueItem.due_at < now)
        .where(ExecutionQueueItem.completed_at.is_(None))
        .where(ExecutionQueueItem.deleted_at.is_(None))
    ).all()
    overdue_inv = db.scalars(
        select(InvestorOpportunity)
        .where(InvestorOpportunity.mission_id == mission_id)
        .where(InvestorOpportunity.next_step_due_at.is_not(None))
        .where(InvestorOpportunity.next_step_due_at < now)
        .where(InvestorOpportunity.deleted_at.is_(None))
    ).all()
    overdue_market = db.scalars(
        select(MarketOpportunity)
        .where(MarketOpportunity.mission_id == mission_id)
        .where(MarketOpportunity.next_step_due_at.is_not(None))
        .where(MarketOpportunity.next_step_due_at < now)
        .where(MarketOpportunity.deleted_at.is_(None))
    ).all()
    overdue_count = len(overdue_queue) + len(overdue_inv) + len(overdue_market)

    pending_approvals = db.scalars(
        select(Approval)
        .where(Approval.mission_id == mission_id)
        .where(Approval.status == "pending")
    ).all()
    pending_approvals_count = len(pending_approvals)

    # Unresolved upstream dependencies — missions we depend_on / blocks /
    # escalates_to that are themselves under strain/critical or paused.
    upstream_edges = db.scalars(
        select(Relationship)
        .where(Relationship.deleted_at.is_(None))
        .where(Relationship.source_type == "mission")
        .where(Relationship.source_id == mission_id)
        .where(Relationship.relationship_type.in_(("depends_on", "blocks", "escalates_to")))
    ).all()
    unresolved = 0
    if upstream_edges:
        target_ids = {e.target_id for e in upstream_edges}
        upstream_missions = db.scalars(
            select(Mission).where(Mission.id.in_(target_ids))
        ).all()
        for m in upstream_missions:
            if m.deleted_at is not None:
                continue
            if m.health_status in ("strain", "critical") or m.status == "paused":
                unresolved += 1
    unresolved_dependencies_count = unresolved

    high_priority_intel = db.scalars(
        select(IntelItem)
        .where(IntelItem.mission_id == mission_id)
        .where(IntelItem.strategic_relevance_score >= 70)
    ).all()
    high_priority_intel_count = len(high_priority_intel)

    activity_events = db.scalars(
        select(OperationalEvent)
        .where(OperationalEvent.mission_id == mission_id)
        .where(OperationalEvent.created_at >= one_hour_ago)
    ).all()
    activity_volume = len(activity_events)

    escalation_flags = db.scalars(
        select(OperationalEvent)
        .where(OperationalEvent.mission_id == mission_id)
        .where(OperationalEvent.created_at >= one_day_ago)
        .where(OperationalEvent.severity.in_(("warning", "critical")))
    ).all()
    escalation_flags_count = len(escalation_flags)

    # ---- scoring ----------------------------------------------------------
    base = W_BASE_FROM_PRIORITY.get(mission.priority, 0)

    blockers_pts = min(W_BLOCKERS_CAP, blockers_count * W_BLOCKERS_PER)
    overdue_pts = min(W_OVERDUE_CAP, overdue_count * W_OVERDUE_PER)
    approvals_pts = min(W_APPROVALS_CAP, pending_approvals_count * W_APPROVALS_PER)
    deps_pts = min(
        W_UNRESOLVED_DEPS_CAP, unresolved_dependencies_count * W_UNRESOLVED_DEPS_PER
    )
    intel_pts = min(W_INTEL_CAP, high_priority_intel_count * W_INTEL_PER)
    activity_pts = min(
        W_ACTIVITY_CAP,
        max(0, activity_volume - W_ACTIVITY_VOLUME_THRESHOLD)
        * W_ACTIVITY_PER_OVER_THRESHOLD,
    )
    escalation_pts = min(
        W_ESCALATION_CAP, escalation_flags_count * W_ESCALATION_PER
    )

    # Sprint 4 — intelligence signal contributions (signed; opportunities relieve).
    signal_total, signal_breakdown = signal_propagation_service.aggregate_pressure_contribution(
        db, mission_id
    )
    signal_pts = max(W_SIGNAL_IMPACT_CAP_NEG, min(W_SIGNAL_IMPACT_CAP_POS, signal_total))

    raw = (
        base
        + blockers_pts
        + overdue_pts
        + approvals_pts
        + deps_pts
        + intel_pts
        + activity_pts
        + escalation_pts
        + signal_pts
    )
    score = max(0, min(100, raw))
    health = _band(score)

    components: dict[str, Any] = {
        "base": base,
        "blockers": blockers_pts,
        "overdue": overdue_pts,
        "pending_approvals": approvals_pts,
        "unresolved_dependencies": deps_pts,
        "high_priority_intel": intel_pts,
        "activity_volume": activity_pts,
        "escalation_flags": escalation_pts,
        "signal_impact": signal_pts,
        "signal_breakdown": signal_breakdown,
    }

    snapshot = MissionPressureSnapshot(
        mission_id=mission_id,
        score=score,
        health_status=health,
        components=components,
        blockers_count=blockers_count,
        overdue_count=overdue_count,
        pending_approvals_count=pending_approvals_count,
        unresolved_dependencies_count=unresolved_dependencies_count,
        high_priority_intel_count=high_priority_intel_count,
        activity_volume=activity_volume,
        escalation_flags_count=escalation_flags_count,
        source=source,
        trigger_event_id=trigger_event_id,
    )

    # Update the mission's denormalized score / health for fast reads.
    mission.pressure_score = score
    mission.health_status = health

    if persist:
        db.add(snapshot)
        db.flush()

    return snapshot


def to_mission_pressure(snap: MissionPressureSnapshot) -> MissionPressure:
    """Adapt a snapshot to the existing /missions/{id}/pressure response."""
    return MissionPressure(
        mission_id=snap.mission_id,
        pressure_score=snap.score,
        health_status=snap.health_status,  # type: ignore[arg-type]
        components=snap.components,
        blockers_count=snap.blockers_count,
        overdue_count=snap.overdue_count,
        pending_approvals_count=snap.pending_approvals_count,
        explanation=(
            f"Pressure {snap.score}/100 ({snap.health_status}) computed from "
            f"{sum(1 for v in snap.components.values() if v != 0)} active "
            f"signal(s). See history for trajectory."
        ),
    )


def list_history(
    db: Session, mission_id: int, *, limit: int = 100
) -> list[MissionPressureSnapshot]:
    db.get(Mission, mission_id) or HTTPException(
        status_code=404, detail=f"Mission #{mission_id} not found"
    )
    rows = db.scalars(
        select(MissionPressureSnapshot)
        .where(MissionPressureSnapshot.mission_id == mission_id)
        .order_by(MissionPressureSnapshot.computed_at.desc())
        .limit(limit)
    ).all()
    return list(rows)


def recompute_for_mission(
    db: Session,
    mission_id: Optional[int],
    *,
    source: str = "trigger",
    trigger_event_id: Optional[int] = None,
) -> Optional[MissionPressureSnapshot]:
    """Convenience wrapper for triggers: silently no-op if mission_id is None
    or the mission was deleted. Used after queue/approval/event mutations."""
    if mission_id is None:
        return None
    mission = db.get(Mission, mission_id)
    if mission is None or mission.deleted_at is not None:
        return None
    return compute_pressure(
        db,
        mission_id,
        persist=True,
        source=source,
        trigger_event_id=trigger_event_id,
    )
