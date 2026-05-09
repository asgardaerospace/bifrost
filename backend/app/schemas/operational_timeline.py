"""Unified operational timeline schemas — Sprint 7.

Cross-mission temporal layer that compresses operational evolution into
a single replayable stream: events, approvals, proposed actions, agent
runs, recommendations, escalations, executive decisions.

Distinct from `services/timeline.py` (per-opportunity) and the per-mission
timeline. This is the org-wide replay surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from app.schemas.base import ORMModel


TimelineEntryKind = Literal[
    "operational_event",
    "approval_decided",
    "proposed_action",
    "agent_run",
    "recommendation",
    "escalation",
    "pressure_shift",
    "workflow_stage",
]


class OperationalTimelineEntry(ORMModel):
    id: str  # stable f"{kind}:{record_id}"
    kind: TimelineEntryKind
    occurred_at: datetime
    title: str
    summary: Optional[str] = None
    severity: Literal["info", "notice", "warn", "critical"] = "info"
    actor: Optional[str] = None
    mission_id: Optional[int] = None
    mission_codename: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    cluster_id: Optional[str] = None
    causal_parent_id: Optional[str] = None
    propagation: list[str] = []  # ids of derived/propagated entries
    data: dict = {}


class OperationalTimelineCluster(ORMModel):
    """A grouping of entries that share a causal chain or topic burst."""

    id: str
    label: str
    started_at: datetime
    ended_at: datetime
    entry_count: int
    severity: Literal["info", "notice", "warn", "critical"]
    mission_ids: list[int] = []
    summary: Optional[str] = None


class OperationalTimelineView(ORMModel):
    generated_at: datetime
    scope: Literal["org", "mission"]
    mission_id: Optional[int] = None
    window_started_at: datetime
    window_ended_at: datetime
    count: int
    counts_by_kind: dict[str, int]
    counts_by_severity: dict[str, int]
    entries: list[OperationalTimelineEntry]
    clusters: list[OperationalTimelineCluster]
