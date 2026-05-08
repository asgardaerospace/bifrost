"""Presence schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.schemas.base import ORMModel


class PresenceSessionRead(ORMModel):
    id: int
    client_id: str
    user_id: Optional[int] = None
    display_name: Optional[str] = None
    mission_id: Optional[int] = None
    connected_at: datetime
    last_heartbeat: datetime
    disconnected_at: Optional[datetime] = None


class PresenceList(ORMModel):
    count: int
    operators: list[PresenceSessionRead]
