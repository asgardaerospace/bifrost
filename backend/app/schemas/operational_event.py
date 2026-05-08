"""Operational event schemas — bus-style awareness signals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from app.schemas.base import ORMModel


EventSeverity = Literal["info", "notice", "warning", "critical"]


class OperationalEventCreate(ORMModel):
    topic: str
    event_type: str
    mission_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    actor: Optional[str] = None
    source: Optional[str] = None
    severity: EventSeverity = "info"
    payload: Optional[dict[str, Any]] = None


class OperationalEventRead(ORMModel):
    id: int
    topic: str
    event_type: str
    mission_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    actor: Optional[str] = None
    source: Optional[str] = None
    severity: EventSeverity
    payload: Optional[dict[str, Any]] = None
    created_at: datetime


class OperationalEventStream(ORMModel):
    count: int
    cursor: Optional[int] = None  # last id seen — clients pass back via ?since
    items: list[OperationalEventRead]
