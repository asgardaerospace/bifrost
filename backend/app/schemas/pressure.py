"""Pressure snapshot schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.schemas.base import ORMModel


class PressureSnapshotRead(ORMModel):
    id: int
    mission_id: int
    score: int
    health_status: str
    components: dict[str, Any]
    blockers_count: int
    overdue_count: int
    pending_approvals_count: int
    unresolved_dependencies_count: int
    high_priority_intel_count: int
    activity_volume: int
    escalation_flags_count: int
    source: str
    trigger_event_id: Optional[int] = None
    computed_at: datetime


class PressureHistory(ORMModel):
    mission_id: int
    count: int
    snapshots: list[PressureSnapshotRead]
