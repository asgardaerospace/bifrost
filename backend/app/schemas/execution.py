"""Execution Queue schemas — ExecutionService surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from app.schemas.base import ORMModel


QueueItemStatus = Literal[
    "queued", "in_progress", "blocked", "completed", "cancelled", "deferred"
]
QueueItemType = Literal[
    "task",
    "approval",
    "draft",
    "followup",
    "recommendation",
    "mission_action",
    "blocker",
]


class ExecutionQueueItemRead(ORMModel):
    id: Optional[int] = None  # None for projected rows that don't have a real id
    item_type: QueueItemType
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    mission_id: Optional[int] = None
    title: str
    summary: Optional[str] = None
    status: QueueItemStatus
    priority_score: int = 0
    pressure_score: int = 0
    owner: Optional[str] = None
    due_at: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    is_projected: bool = False
    requires_approval: bool = False
    meta: Optional[dict[str, Any]] = None


class ExecutionQueue(ORMModel):
    count: int
    items: list[ExecutionQueueItemRead]


class ExecutionQueueItemCreate(ORMModel):
    item_type: QueueItemType
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    mission_id: Optional[int] = None
    title: str
    summary: Optional[str] = None
    priority_score: int = 0
    pressure_score: int = 0
    owner: Optional[str] = None
    due_at: Optional[datetime] = None
    requires_approval: bool = False
    meta: Optional[dict[str, Any]] = None


class ExecutionQueueItemUpdate(ORMModel):
    status: Optional[QueueItemStatus] = None
    priority_score: Optional[int] = None
    pressure_score: Optional[int] = None
    owner: Optional[str] = None
    due_at: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    meta: Optional[dict[str, Any]] = None
