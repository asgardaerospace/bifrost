"""Unified operational timeline — Sprint 7.

Pulls together heterogeneous operational records into a single replayable
stream. Sources:

    - operational_events            (the event bus)
    - approvals (decided)           (governance closures)
    - proposed_actions              (autonomy proposals)
    - autonomy_operations           (agent runs)
    - mission_pressure_snapshots    (pressure shifts > threshold)

Clustering: temporal bursts on the same mission within a 30-minute window
are grouped, so the cockpit can render a single "incident" rather than a
firehose. Causal parents are derived from autonomy_operation_id linkage.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.autonomy import AutonomyOperation, ProposedAction
from app.models.mission import Mission
from app.models.operational_event import OperationalEvent
from app.models.pressure_snapshot import MissionPressureSnapshot
from app.schemas.operational_timeline import (
    OperationalTimelineCluster,
    OperationalTimelineEntry,
    OperationalTimelineView,
)


_DEFAULT_WINDOW_HOURS = 24
_CLUSTER_WINDOW_MIN = 30
_PRESSURE_DELTA_MIN = 10  # only surface snapshots that move the score this much


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _severity_from_event(ev: OperationalEvent) -> str:
    s = (ev.severity or "info").lower()
    if s in ("info", "notice", "warn", "critical"):
        return s
    return "info"


def _entry_for_event(ev: OperationalEvent, mission_codename: Optional[str]) -> OperationalTimelineEntry:
    payload = ev.payload or {}
    summary = (
        payload.get("summary")
        if isinstance(payload, dict)
        else None
    )
    return OperationalTimelineEntry(
        id=f"event:{ev.id}",
        kind="operational_event",
        occurred_at=ev.created_at,
        title=ev.event_type,
        summary=summary,
        severity=_severity_from_event(ev),  # type: ignore[arg-type]
        actor=ev.actor,
        mission_id=ev.mission_id,
        mission_codename=mission_codename,
        entity_type=ev.entity_type,
        entity_id=ev.entity_id,
        data={"topic": ev.topic, "source": ev.source, "payload": payload},
    )


def _entry_for_approval(a: Approval, mission_codename: Optional[str]) -> OperationalTimelineEntry:
    when = a.reviewed_at or a.created_at
    severity = "notice" if a.status == "approved" else "warn" if a.status == "rejected" else "info"
    return OperationalTimelineEntry(
        id=f"approval:{a.id}",
        kind="approval_decided",
        occurred_at=when,
        title=f"Approval {a.status}: {a.action}",
        summary=a.decision_note,
        severity=severity,  # type: ignore[arg-type]
        actor=a.reviewer or a.requested_by,
        mission_id=a.mission_id,
        mission_codename=mission_codename,
        entity_type=a.entity_type,
        entity_id=a.entity_id,
        data={"workflow_run_id": a.workflow_run_id},
    )


def _entry_for_proposed(pa: ProposedAction, op: AutonomyOperation, mission_codename: Optional[str]) -> OperationalTimelineEntry:
    severity = "notice" if pa.status == "approved" else "warn" if pa.status == "rejected" else "info"
    return OperationalTimelineEntry(
        id=f"proposed:{pa.id}",
        kind="proposed_action",
        occurred_at=pa.created_at,
        title=f"Proposed {pa.action_type} ({pa.status})",
        summary=op.reasoning,
        severity=severity,  # type: ignore[arg-type]
        actor=op.agent_name,
        mission_id=op.mission_id,
        mission_codename=mission_codename,
        entity_type=pa.target_entity_type,
        entity_id=pa.target_entity_id,
        causal_parent_id=f"agent_run:{op.id}",
        data={
            "operation_id": op.id,
            "requires_approval": pa.requires_approval,
            "confidence": op.confidence_score,
        },
    )


def _entry_for_op(op: AutonomyOperation, mission_codename: Optional[str]) -> OperationalTimelineEntry:
    severity = "info" if op.status in ("proposed", "executed", "approved") else "warn"
    return OperationalTimelineEntry(
        id=f"agent_run:{op.id}",
        kind="agent_run",
        occurred_at=op.proposed_at,
        title=f"{op.agent_name} run ({op.status})",
        summary=op.reasoning,
        severity=severity,  # type: ignore[arg-type]
        actor=op.agent_name,
        mission_id=op.mission_id,
        mission_codename=mission_codename,
        entity_type="autonomy_operation",
        entity_id=op.id,
        data={
            "workflow_key": op.workflow_key,
            "trigger": op.trigger,
            "confidence": op.confidence_score,
        },
    )


def _entry_for_pressure_shift(
    prev: MissionPressureSnapshot,
    curr: MissionPressureSnapshot,
    mission_codename: Optional[str],
) -> Optional[OperationalTimelineEntry]:
    delta = int(curr.score) - int(prev.score)
    if abs(delta) < _PRESSURE_DELTA_MIN:
        return None
    direction = "↑" if delta > 0 else "↓"
    severity = "critical" if curr.health_status == "critical" else "warn" if curr.health_status == "strain" else "notice"
    return OperationalTimelineEntry(
        id=f"pressure:{curr.id}",
        kind="pressure_shift",
        occurred_at=curr.computed_at,
        title=f"Pressure {direction}{abs(delta)} → {curr.score} ({curr.health_status})",
        summary=f"Score moved from {prev.score} to {curr.score}.",
        severity=severity,  # type: ignore[arg-type]
        mission_id=curr.mission_id,
        mission_codename=mission_codename,
        entity_type="mission",
        entity_id=curr.mission_id,
        data={
            "prev_score": prev.score,
            "current_score": curr.score,
            "delta": delta,
            "components": curr.components,
        },
    )


def _hydrate_codenames(db: Session, mission_ids: Iterable[Optional[int]]) -> dict[int, str]:
    ids = {mid for mid in mission_ids if mid is not None}
    if not ids:
        return {}
    return {
        m.id: m.codename
        for m in db.scalars(select(Mission).where(Mission.id.in_(ids))).all()
    }


def _cluster_entries(entries: list[OperationalTimelineEntry]) -> list[OperationalTimelineCluster]:
    """Group entries that share a mission and fall inside a sliding 30-min
    window into a single cluster. Calm visualization aid."""
    clusters: list[OperationalTimelineCluster] = []
    if not entries:
        return clusters
    # entries must be sorted oldest first for clustering
    by_mission: dict[Optional[int], list[OperationalTimelineEntry]] = {}
    for e in entries:
        by_mission.setdefault(e.mission_id, []).append(e)

    severity_rank = {"info": 0, "notice": 1, "warn": 2, "critical": 3}

    for mission_id, group in by_mission.items():
        group.sort(key=lambda x: x.occurred_at)
        bucket: list[OperationalTimelineEntry] = []
        for e in group:
            if not bucket:
                bucket.append(e)
                continue
            window_start = bucket[0].occurred_at
            if (e.occurred_at - window_start).total_seconds() <= _CLUSTER_WINDOW_MIN * 60:
                bucket.append(e)
            else:
                clusters.append(_cluster_from_bucket(bucket, severity_rank))
                bucket = [e]
        if bucket:
            clusters.append(_cluster_from_bucket(bucket, severity_rank))

    # tag entries with their cluster id
    for c in clusters:
        for e in entries:
            if e.mission_id in c.mission_ids and c.started_at <= e.occurred_at <= c.ended_at:
                e.cluster_id = c.id
    # Only return clusters with >= 2 entries — singletons aren't clusters
    return [c for c in clusters if c.entry_count >= 2]


def _cluster_from_bucket(
    bucket: list[OperationalTimelineEntry], severity_rank: dict[str, int]
) -> OperationalTimelineCluster:
    started = min(e.occurred_at for e in bucket)
    ended = max(e.occurred_at for e in bucket)
    mission_ids = sorted({e.mission_id for e in bucket if e.mission_id is not None})
    sev = max(bucket, key=lambda e: severity_rank.get(e.severity, 0)).severity
    label_kinds = sorted({e.kind for e in bucket})
    cid = f"cluster:m{mission_ids[0] if mission_ids else 0}:{int(started.timestamp())}"
    return OperationalTimelineCluster(
        id=cid,
        label=" + ".join(label_kinds),
        started_at=started,
        ended_at=ended,
        entry_count=len(bucket),
        severity=sev,  # type: ignore[arg-type]
        mission_ids=mission_ids,
        summary=(
            f"{len(bucket)} entries over "
            f"{int((ended - started).total_seconds() // 60)} min"
        ),
    )


def build_timeline(
    db: Session,
    *,
    mission_id: Optional[int] = None,
    hours: int = _DEFAULT_WINDOW_HOURS,
    limit: int = 250,
) -> OperationalTimelineView:
    end = _now()
    start = end - timedelta(hours=max(1, min(hours, 24 * 14)))

    # ----- collect raw rows ------------------------------------------------
    ev_stmt = (
        select(OperationalEvent)
        .where(OperationalEvent.created_at >= start)
        .order_by(OperationalEvent.created_at.desc())
        .limit(limit)
    )
    if mission_id is not None:
        ev_stmt = ev_stmt.where(OperationalEvent.mission_id == mission_id)
    events = list(db.scalars(ev_stmt).all())

    appr_stmt = select(Approval).where(Approval.reviewed_at.is_not(None)).where(
        Approval.reviewed_at >= start
    )
    if mission_id is not None:
        appr_stmt = appr_stmt.where(Approval.mission_id == mission_id)
    approvals = list(db.scalars(appr_stmt).all())

    op_stmt = (
        select(AutonomyOperation)
        .where(AutonomyOperation.proposed_at >= start)
        .order_by(AutonomyOperation.proposed_at.desc())
    )
    if mission_id is not None:
        op_stmt = op_stmt.where(AutonomyOperation.mission_id == mission_id)
    ops = list(db.scalars(op_stmt).all())
    op_by_id = {o.id: o for o in ops}

    pa_stmt = select(ProposedAction).where(ProposedAction.created_at >= start)
    if mission_id is not None:
        pa_stmt = pa_stmt.where(
            ProposedAction.autonomy_operation_id.in_(
                [o.id for o in ops] or [-1]
            )
        )
    proposed = list(db.scalars(pa_stmt).all())

    snap_stmt = (
        select(MissionPressureSnapshot)
        .where(MissionPressureSnapshot.computed_at >= start)
        .order_by(MissionPressureSnapshot.computed_at.asc())
    )
    if mission_id is not None:
        snap_stmt = snap_stmt.where(MissionPressureSnapshot.mission_id == mission_id)
    snaps = list(db.scalars(snap_stmt).all())

    # ----- derive entries --------------------------------------------------
    mission_ids = (
        {ev.mission_id for ev in events}
        | {a.mission_id for a in approvals}
        | {o.mission_id for o in ops}
        | {s.mission_id for s in snaps}
    )
    codenames = _hydrate_codenames(db, mission_ids)

    entries: list[OperationalTimelineEntry] = []
    for ev in events:
        entries.append(_entry_for_event(ev, codenames.get(ev.mission_id) if ev.mission_id else None))
    for a in approvals:
        entries.append(_entry_for_approval(a, codenames.get(a.mission_id) if a.mission_id else None))
    for o in ops:
        entries.append(_entry_for_op(o, codenames.get(o.mission_id) if o.mission_id else None))
    for pa in proposed:
        op = op_by_id.get(pa.autonomy_operation_id)
        if op is None:
            op = db.get(AutonomyOperation, pa.autonomy_operation_id)
            if op is not None:
                op_by_id[op.id] = op
        if op is None:
            continue
        entries.append(_entry_for_proposed(pa, op, codenames.get(op.mission_id) if op.mission_id else None))

    # pressure shifts: compare each snapshot to the previous one for that mission
    snaps_by_mission: dict[int, list[MissionPressureSnapshot]] = {}
    for s in snaps:
        snaps_by_mission.setdefault(s.mission_id, []).append(s)
    for mid, ss in snaps_by_mission.items():
        ss.sort(key=lambda x: x.computed_at)
        for i in range(1, len(ss)):
            entry = _entry_for_pressure_shift(ss[i - 1], ss[i], codenames.get(mid))
            if entry is not None:
                entries.append(entry)

    # sort newest first, cap
    entries.sort(key=lambda e: e.occurred_at, reverse=True)
    entries = entries[:limit]

    # cluster (oldest-first internally)
    clusters = _cluster_entries(list(entries))

    counts_by_kind: dict[str, int] = {}
    counts_by_severity: dict[str, int] = {}
    for e in entries:
        counts_by_kind[e.kind] = counts_by_kind.get(e.kind, 0) + 1
        counts_by_severity[e.severity] = counts_by_severity.get(e.severity, 0) + 1

    return OperationalTimelineView(
        generated_at=_now(),
        scope="mission" if mission_id is not None else "org",
        mission_id=mission_id,
        window_started_at=start,
        window_ended_at=end,
        count=len(entries),
        counts_by_kind=counts_by_kind,
        counts_by_severity=counts_by_severity,
        entries=entries,
        clusters=clusters,
    )
