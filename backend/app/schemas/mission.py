"""Mission schemas — canonical doctrine entity (MissionService surface)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import Field

from app.schemas.base import ORMModel, TimestampedRead


MissionStatus = Literal["planning", "active", "paused", "completed", "cancelled"]
MissionPriority = Literal["low", "normal", "high", "critical"]
MissionHealth = Literal["nominal", "watch", "strain", "critical"]


class MissionBase(ORMModel):
    codename: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    mission_type: str = "strategic"
    status: MissionStatus = "planning"
    priority: MissionPriority = "normal"
    pressure_score: int = 0
    health_status: MissionHealth = "nominal"
    owner_user_id: Optional[int] = None
    parent_mission_id: Optional[int] = None
    starts_at: Optional[datetime] = None
    target_completion_at: Optional[datetime] = None


class MissionCreate(MissionBase):
    pass


class MissionUpdate(ORMModel):
    name: Optional[str] = None
    description: Optional[str] = None
    mission_type: Optional[str] = None
    status: Optional[MissionStatus] = None
    priority: Optional[MissionPriority] = None
    pressure_score: Optional[int] = None
    health_status: Optional[MissionHealth] = None
    owner_user_id: Optional[int] = None
    parent_mission_id: Optional[int] = None
    starts_at: Optional[datetime] = None
    target_completion_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MissionRead(MissionBase, TimestampedRead):
    completed_at: Optional[datetime] = None


class MissionEntityCreate(ORMModel):
    entity_type: str
    entity_id: int
    relationship_type: str = "linked"
    weight: int = 1
    notes: Optional[str] = None


class MissionEntityRead(ORMModel):
    id: int
    mission_id: int
    entity_type: str
    entity_id: int
    relationship_type: str
    weight: int
    notes: Optional[str] = None
    created_at: datetime


class MissionPressure(ORMModel):
    """Pressure scaffold — deterministic placeholder until Sprint 2 model."""

    mission_id: int
    pressure_score: int
    health_status: MissionHealth
    components: dict[str, Any]
    blockers_count: int
    overdue_count: int
    pending_approvals_count: int
    explanation: str


class MissionDependencyEdge(ORMModel):
    relationship_type: str
    other_mission_id: int
    other_codename: Optional[str] = None
    other_name: Optional[str] = None
    direction: Literal["upstream", "downstream"]


class MissionDependencies(ORMModel):
    mission_id: int
    upstream: list[MissionDependencyEdge]
    downstream: list[MissionDependencyEdge]


class MissionTimelineItem(ORMModel):
    item_type: str
    item_id: int
    occurred_at: datetime
    title: str
    summary: Optional[str] = None
    actor: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    data: Optional[dict[str, Any]] = None


class MissionTimeline(ORMModel):
    mission_id: int
    count: int
    items: list[MissionTimelineItem]
