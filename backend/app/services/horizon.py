"""Executive Horizon service — Sprint 7.

Strategic awareness aggregator. Produces a compressed read of the entire
operational habitat suitable for the executive cockpit. Reads only from
canonical state; persists nothing.

The horizon is intentionally calm: it answers *what matters now*, not
*everything that exists*.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.autonomy import AutonomyOperation, ProposedAction
from app.models.execution_queue import ExecutionQueueItem
from app.models.intel import IntelItem
from app.models.mission import Mission
from app.models.operational_event import OperationalEvent
from app.models.pressure_snapshot import MissionPressureSnapshot
from app.models.task import Task
from app.schemas.horizon import (
    HorizonBand,
    HorizonEscalation,
    HorizonMissionPulse,
    HorizonOpportunity,
    HorizonPressureMap,
    HorizonTempo,
    HorizonView,
)
from app.services import executive as executive_service
from app.services import recommendations as recommendations_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _delta_score_24h(db: Session, mission_id: int, current_score: int) -> int:
    """Score change vs the closest snapshot ~24h ago. Returns 0 if no history."""
    since = _now() - timedelta(hours=24)
    prior = db.scalars(
        select(MissionPressureSnapshot)
        .where(MissionPressureSnapshot.mission_id == mission_id)
        .where(MissionPressureSnapshot.computed_at <= since)
        .order_by(MissionPressureSnapshot.computed_at.desc())
        .limit(1)
    ).first()
    if prior is None:
        return 0
    return int(current_score - prior.score)


def _last_event_at(db: Session, mission_id: int) -> Optional[datetime]:
    return db.scalar(
        select(func.max(OperationalEvent.created_at)).where(
            OperationalEvent.mission_id == mission_id
        )
    )


def _band_for_score(score: int) -> HorizonBand:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "strain"
    if score >= 35:
        return "watch"
    return "nominal"


def _mission_pulse(db: Session, mission: Mission) -> HorizonMissionPulse:
    blockers = (
        db.scalar(
            select(func.count(ExecutionQueueItem.id))
            .where(ExecutionQueueItem.mission_id == mission.id)
            .where(ExecutionQueueItem.status == "blocked")
            .where(ExecutionQueueItem.deleted_at.is_(None))
        )
        or 0
    )
    blockers += (
        db.scalar(
            select(func.count(Task.id))
            .where(Task.mission_id == mission.id)
            .where(Task.status == "blocked")
            .where(Task.deleted_at.is_(None))
        )
        or 0
    )

    now = _now()
    overdue = (
        db.scalar(
            select(func.count(ExecutionQueueItem.id))
            .where(ExecutionQueueItem.mission_id == mission.id)
            .where(ExecutionQueueItem.due_at.is_not(None))
            .where(ExecutionQueueItem.due_at < now)
            .where(ExecutionQueueItem.completed_at.is_(None))
            .where(ExecutionQueueItem.deleted_at.is_(None))
        )
        or 0
    )

    pending_approvals = (
        db.scalar(
            select(func.count(Approval.id))
            .where(Approval.mission_id == mission.id)
            .where(Approval.status == "pending")
        )
        or 0
    )

    open_proposed = (
        db.scalar(
            select(func.count(ProposedAction.id))
            .join(
                AutonomyOperation,
                AutonomyOperation.id == ProposedAction.autonomy_operation_id,
            )
            .where(AutonomyOperation.mission_id == mission.id)
            .where(ProposedAction.status == "pending")
        )
        or 0
    )

    return HorizonMissionPulse(
        mission_id=mission.id,
        codename=mission.codename,
        name=mission.name,
        priority=mission.priority,
        health_status=_band_for_score(mission.pressure_score or 0),
        pressure_score=int(mission.pressure_score or 0),
        pressure_delta_24h=_delta_score_24h(db, mission.id, mission.pressure_score or 0),
        blockers=int(blockers),
        overdue=int(overdue),
        pending_approvals=int(pending_approvals),
        open_proposed_actions=int(open_proposed),
        last_event_at=_last_event_at(db, mission.id),
    )


def _pressure_map(missions: list[Mission]) -> HorizonPressureMap:
    bands = {"nominal": 0, "watch": 0, "strain": 0, "critical": 0}
    total = 0
    peak = -1
    peak_id: Optional[int] = None
    peak_codename: Optional[str] = None
    for m in missions:
        score = int(m.pressure_score or 0)
        band = _band_for_score(score)
        bands[band] += 1
        total += score
        if score > peak:
            peak = score
            peak_id = m.id
            peak_codename = m.codename
    avg = int(total / len(missions)) if missions else 0
    return HorizonPressureMap(
        nominal=bands["nominal"],
        watch=bands["watch"],
        strain=bands["strain"],
        critical=bands["critical"],
        average_score=avg,
        peak_score=max(0, peak),
        peak_mission_id=peak_id,
        peak_mission_codename=peak_codename,
    )


def _tempo(db: Session) -> HorizonTempo:
    now = _now()
    one_hr = now - timedelta(hours=1)
    one_day = now - timedelta(hours=24)

    events_hr = (
        db.scalar(
            select(func.count(OperationalEvent.id)).where(
                OperationalEvent.created_at >= one_hr
            )
        )
        or 0
    )
    events_day = (
        db.scalar(
            select(func.count(OperationalEvent.id)).where(
                OperationalEvent.created_at >= one_day
            )
        )
        or 0
    )
    approvals_decided = (
        db.scalar(
            select(func.count(Approval.id))
            .where(Approval.reviewed_at.is_not(None))
            .where(Approval.reviewed_at >= one_day)
        )
        or 0
    )
    proposed_decided = (
        db.scalar(
            select(func.count(ProposedAction.id))
            .where(ProposedAction.status.in_(("approved", "rejected")))
            .where(ProposedAction.updated_at >= one_day)
        )
        or 0
    )
    agent_runs = (
        db.scalar(
            select(func.count(AutonomyOperation.id)).where(
                AutonomyOperation.proposed_at >= one_day
            )
        )
        or 0
    )
    workflows_completed = (
        db.scalar(
            select(func.count(AutonomyOperation.id))
            .where(AutonomyOperation.proposed_at >= one_day)
            .where(AutonomyOperation.status.in_(("proposed", "approved", "executed")))
        )
        or 0
    )

    return HorizonTempo(
        events_last_hour=int(events_hr),
        events_last_24h=int(events_day),
        approvals_decided_24h=int(approvals_decided),
        proposed_actions_decided_24h=int(proposed_decided),
        agent_runs_24h=int(agent_runs),
        workflows_completed_24h=int(workflows_completed),
    )


def _escalations(db: Session, limit: int = 8) -> list[HorizonEscalation]:
    """Critical-band signals — pulled from the executive alert bundle plus
    high-relevance intel items not yet acknowledged."""
    bundle = executive_service.build_alerts(db)
    out: list[HorizonEscalation] = []
    for alert in bundle.alerts[:limit]:
        out.append(
            HorizonEscalation(
                id=alert.id,
                severity=alert.severity,
                domain=alert.domain,
                title=alert.title,
                detail=alert.description,
                related_entity_type=alert.related_entity_type,
                related_entity_id=alert.related_entity_id,
                link_hint=alert.link_hint,
            )
        )

    if len(out) < limit:
        # High-urgency intel adds escalation context.
        intel_rows = db.scalars(
            select(IntelItem)
            .where(IntelItem.urgency_score >= 75)
            .order_by(IntelItem.published_at.desc().nullslast())
            .limit(limit - len(out))
        ).all()
        for r in intel_rows:
            out.append(
                HorizonEscalation(
                    id=f"intel.urgency.{r.id}",
                    severity="warn",
                    domain="intel",
                    title=r.title[:140],
                    detail=(r.summary or "Time-sensitive intel signal.")[:280],
                    mission_id=r.mission_id,
                    related_entity_type="intel_item",
                    related_entity_id=r.id,
                    link_hint="/intel",
                )
            )
    # Attach mission codenames where available.
    mission_ids = {e.mission_id for e in out if e.mission_id is not None}
    if mission_ids:
        codenames = {
            m.id: m.codename
            for m in db.scalars(
                select(Mission).where(Mission.id.in_(mission_ids))
            ).all()
        }
        for e in out:
            if e.mission_id is not None:
                e.mission_codename = codenames.get(e.mission_id)
    return out


def _opportunities(db: Session, limit: int = 6) -> list[HorizonOpportunity]:
    bundle = recommendations_service.build_recommendations(db, limit=limit * 3)
    seen: set[str] = set()
    out: list[HorizonOpportunity] = []
    for rec in bundle.recommendations:
        if rec.id in seen:
            continue
        seen.add(rec.id)
        primary = rec.related_entities[0] if rec.related_entities else None
        out.append(
            HorizonOpportunity(
                id=rec.id,
                domain=rec.type,
                title=rec.headline,
                detail=rec.reasoning,
                confidence=int(rec.confidence_score),
                related_entity_type=primary.type if primary else None,
                related_entity_id=primary.id if primary else None,
                link_hint=rec.link_hint,
            )
        )
        if len(out) >= limit:
            break
    return out


def _narrative(
    pressure_map: HorizonPressureMap,
    tempo: HorizonTempo,
    escalations: list[HorizonEscalation],
    opportunities: list[HorizonOpportunity],
) -> list[str]:
    out: list[str] = []
    if pressure_map.critical:
        out.append(
            f"{pressure_map.critical} mission(s) in critical pressure — operational saturation."
        )
    elif pressure_map.strain:
        out.append(f"{pressure_map.strain} mission(s) under strain.")
    if tempo.events_last_hour >= 25:
        out.append(f"Tempo elevated: {tempo.events_last_hour} events in the last hour.")
    crit = sum(1 for e in escalations if e.severity == "critical")
    if crit:
        out.append(f"{crit} critical escalation(s) require immediate attention.")
    if opportunities:
        out.append(
            f"{len(opportunities)} strategic opportunit(ies) surfaced from the relationship graph."
        )
    if not out:
        out.append("Operational habitat is calm. No critical pressure detected.")
    return out


def _headline_band(pressure_map: HorizonPressureMap, escalations: list[HorizonEscalation]) -> HorizonBand:
    crit_alerts = sum(1 for e in escalations if e.severity == "critical")
    if pressure_map.critical or crit_alerts >= 2:
        return "critical"
    if pressure_map.strain or crit_alerts >= 1:
        return "strain"
    if pressure_map.watch:
        return "watch"
    return "nominal"


def build_horizon(db: Session, *, top_n: int = 6) -> HorizonView:
    missions = list(
        db.scalars(
            select(Mission).where(Mission.deleted_at.is_(None))
        ).all()
    )
    pressure_map = _pressure_map(missions)
    tempo = _tempo(db)
    escalations = _escalations(db)
    opportunities = _opportunities(db)

    # Top missions: highest pressure first, ties broken by priority.
    priority_rank = {"critical": 0, "high": 1, "normal": 2, "low": 3}
    sorted_missions = sorted(
        missions,
        key=lambda m: (
            -(m.pressure_score or 0),
            priority_rank.get(m.priority, 4),
            m.id,
        ),
    )
    top_missions = [_mission_pulse(db, m) for m in sorted_missions[:top_n]]

    band = _headline_band(pressure_map, escalations)
    headline = (
        f"{pressure_map.critical} critical · {pressure_map.strain} strain · "
        f"{len(escalations)} escalation(s) · tempo {tempo.events_last_hour}/hr"
    )

    return HorizonView(
        generated_at=_now(),
        headline=headline,
        band=band,
        pressure_map=pressure_map,
        tempo=tempo,
        top_missions=top_missions,
        escalations=escalations,
        opportunities=opportunities,
        narrative=_narrative(pressure_map, tempo, escalations, opportunities),
    )
