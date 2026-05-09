"""Executive Horizon schemas — Sprint 7.

The Executive Horizon is a strategic awareness surface — a calm, compressed
read of the operational habitat. It deliberately sits *above* the action
queue / alert / briefing surfaces (which it consumes) and answers four
operator questions:

    1. What matters most right now?
    2. What is escalating?
    3. Where is operational pressure increasing?
    4. Where is strategic opportunity emerging?

The schema is intentionally sparse — no per-domain dashboards, no spreadsheet
filters. Aggregation lives in services/horizon.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from app.schemas.base import ORMModel


HorizonBand = Literal["nominal", "watch", "strain", "critical"]


class HorizonMissionPulse(ORMModel):
    """One mission's compressed strategic signal."""

    mission_id: int
    codename: str
    name: str
    priority: str
    health_status: HorizonBand
    pressure_score: int
    pressure_delta_24h: int = 0  # change vs the snapshot ~24h ago
    blockers: int = 0
    overdue: int = 0
    pending_approvals: int = 0
    open_proposed_actions: int = 0
    last_event_at: Optional[datetime] = None


class HorizonEscalation(ORMModel):
    """An active escalation surface."""

    id: str
    severity: Literal["info", "warn", "critical"]
    domain: str
    title: str
    detail: str
    mission_id: Optional[int] = None
    mission_codename: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    link_hint: Optional[str] = None


class HorizonOpportunity(ORMModel):
    """An emerging strategic opportunity surface."""

    id: str
    domain: str
    title: str
    detail: str
    confidence: int
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    link_hint: Optional[str] = None


class HorizonTempo(ORMModel):
    """Global operational tempo — calm telemetry only."""

    events_last_hour: int
    events_last_24h: int
    approvals_decided_24h: int
    proposed_actions_decided_24h: int
    agent_runs_24h: int
    workflows_completed_24h: int


class HorizonPressureMap(ORMModel):
    """Mission-by-band aggregation for the org-wide pressure map."""

    nominal: int
    watch: int
    strain: int
    critical: int
    average_score: int
    peak_score: int
    peak_mission_id: Optional[int] = None
    peak_mission_codename: Optional[str] = None


class HorizonView(ORMModel):
    generated_at: datetime
    headline: str
    band: HorizonBand
    pressure_map: HorizonPressureMap
    tempo: HorizonTempo
    top_missions: list[HorizonMissionPulse]
    escalations: list[HorizonEscalation]
    opportunities: list[HorizonOpportunity]
    narrative: list[str]
