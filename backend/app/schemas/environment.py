"""Environmental telemetry schemas — Sprint 7.

A calm operational habitat reads. The environment layer is what the shell
chrome animates against — ambient pressure, propagation pulse rates, agent
activity, escalation surface counts.

This is NOT a metrics dashboard; it is the *atmosphere* the cockpit lives
in. The frontend uses these signals to drive subtle, non-decorative motion
(elevation shifts, edge intensity, ambient glow tied to band changes).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from app.schemas.base import ORMModel


EnvironmentBand = Literal["calm", "active", "elevated", "critical"]


class EnvironmentPulse(ORMModel):
    """One-tick reading of operational atmosphere."""

    generated_at: datetime
    band: EnvironmentBand
    pressure_index: int  # 0..100 normalized weighted-average mission pressure
    propagation_index: int  # 0..100 — relationship traffic intensity (last hour)
    activity_rate: int  # operational events / hour
    escalation_count: int  # active critical/warning alerts
    open_proposed_actions: int
    active_agent_runs: int
    presence_count: int  # active operator presences
    realtime_subscribers: int


class EnvironmentTrend(ORMModel):
    """Recent environmental trajectory — used for ambient motion pacing."""

    pulses: list[EnvironmentPulse]
    pressure_delta: int  # positive = rising
    propagation_delta: int
    activity_delta: int


class EnvironmentSnapshot(ORMModel):
    pulse: EnvironmentPulse
    trend: EnvironmentTrend
    narrative: list[str]
