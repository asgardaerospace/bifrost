"""Environmental telemetry service — Sprint 7.

The "atmosphere" of the operational habitat — a calm, normalized read of
pressure / propagation / activity / escalation that the cockpit shell uses
to drive ambient motion (depth shifts, glow intensity, edge breathing).

Designed to be called frequently (sub-minute). All values are cheap to
compute. Trends compose from in-memory ring buffer that survives across
calls within the process; for multi-worker deployments the ring re-warms
after a handful of ticks (acceptable — these are *atmosphere* signals).
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.autonomy import AutonomyOperation, ProposedAction
from app.models.mission import Mission
from app.models.operational_event import OperationalEvent
from app.schemas.environment import (
    EnvironmentBand,
    EnvironmentPulse,
    EnvironmentSnapshot,
    EnvironmentTrend,
)
from app.services import executive as executive_service
from app.services import presence as presence_service
from app.services.pubsub import manager as pubsub_manager


_RING: Deque[EnvironmentPulse] = deque(maxlen=24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _band(pressure: int, propagation: int, escalations: int) -> EnvironmentBand:
    if escalations >= 3 or pressure >= 75:
        return "critical"
    if pressure >= 55 or propagation >= 60 or escalations >= 1:
        return "elevated"
    if pressure >= 30 or propagation >= 30:
        return "active"
    return "calm"


def _propagation_index(activity_rate: int, open_proposed: int) -> int:
    """Heuristic propagation pressure: 60% recent event throughput, 40%
    pending autonomous proposals (which bind to humans). Capped at 100."""
    return min(100, int(activity_rate * 0.6 + open_proposed * 4))


def compute_pulse(db: Session) -> EnvironmentPulse:
    now = _now()
    one_hour_ago = now - timedelta(hours=1)

    # weighted-average pressure across active missions
    rows = db.execute(
        select(Mission.pressure_score, Mission.priority)
        .where(Mission.deleted_at.is_(None))
    ).all()
    weights = {"critical": 3, "high": 2, "normal": 1, "low": 1}
    total_w = 0
    total_score = 0
    for score, priority in rows:
        w = weights.get(priority, 1)
        total_w += w
        total_score += int(score or 0) * w
    pressure_index = int(total_score / total_w) if total_w else 0

    activity_rate = (
        db.scalar(
            select(func.count(OperationalEvent.id)).where(
                OperationalEvent.created_at >= one_hour_ago
            )
        )
        or 0
    )

    open_proposed = (
        db.scalar(
            select(func.count(ProposedAction.id)).where(
                ProposedAction.status == "pending"
            )
        )
        or 0
    )
    active_runs = (
        db.scalar(
            select(func.count(AutonomyOperation.id)).where(
                AutonomyOperation.status == "running"
            )
        )
        or 0
    )

    propagation_index = _propagation_index(int(activity_rate), int(open_proposed))

    # escalations from the existing executive alert path
    alert_bundle = executive_service.build_alerts(db)
    escalation_count = alert_bundle.counts_by_severity.get("critical", 0) + alert_bundle.counts_by_severity.get(
        "warn", 0
    )

    presence_count = len(presence_service.list_active(db))

    realtime_subscribers = 0
    try:
        realtime_subscribers = pubsub_manager.connection_count
    except Exception:
        # pubsub manager is best-effort — atmosphere reading must not fail
        # because of websocket plumbing.
        realtime_subscribers = 0

    pulse = EnvironmentPulse(
        generated_at=now,
        band=_band(pressure_index, propagation_index, alert_bundle.counts_by_severity.get("critical", 0)),
        pressure_index=pressure_index,
        propagation_index=propagation_index,
        activity_rate=int(activity_rate),
        escalation_count=int(escalation_count),
        open_proposed_actions=int(open_proposed),
        active_agent_runs=int(active_runs),
        presence_count=int(presence_count),
        realtime_subscribers=int(realtime_subscribers),
    )
    return pulse


def push_pulse(pulse: EnvironmentPulse) -> None:
    _RING.append(pulse)


def trend() -> EnvironmentTrend:
    pulses = list(_RING)
    pressure_delta = 0
    propagation_delta = 0
    activity_delta = 0
    if len(pulses) >= 2:
        first = pulses[0]
        last = pulses[-1]
        pressure_delta = last.pressure_index - first.pressure_index
        propagation_delta = last.propagation_index - first.propagation_index
        activity_delta = last.activity_rate - first.activity_rate
    return EnvironmentTrend(
        pulses=pulses,
        pressure_delta=pressure_delta,
        propagation_delta=propagation_delta,
        activity_delta=activity_delta,
    )


def _narrative(pulse: EnvironmentPulse, t: EnvironmentTrend) -> list[str]:
    out: list[str] = []
    if pulse.band == "critical":
        out.append("Habitat pressure critical — multiple escalation surfaces active.")
    elif pulse.band == "elevated":
        out.append("Habitat tempo elevated. Monitor escalation queue.")
    elif pulse.band == "active":
        out.append("Habitat active. Pressure and propagation in normal operating envelope.")
    else:
        out.append("Habitat calm.")
    if t.pressure_delta >= 5:
        out.append(f"Pressure trending up (+{t.pressure_delta}).")
    elif t.pressure_delta <= -5:
        out.append(f"Pressure trending down ({t.pressure_delta}).")
    if t.propagation_delta >= 10:
        out.append(f"Propagation accelerating (+{t.propagation_delta}).")
    return out


def build_snapshot(db: Session) -> EnvironmentSnapshot:
    pulse = compute_pulse(db)
    push_pulse(pulse)
    t = trend()
    return EnvironmentSnapshot(pulse=pulse, trend=t, narrative=_narrative(pulse, t))
