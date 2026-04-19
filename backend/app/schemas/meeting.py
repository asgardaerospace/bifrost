from datetime import datetime
from typing import Optional

from app.schemas.base import ORMModel, TimestampedRead


class MeetingBase(ORMModel):
    entity_type: str
    entity_id: int
    title: str
    location: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    raw_notes: Optional[str] = None
    outcome: Optional[str] = None
    next_step: Optional[str] = None


class MeetingCreate(MeetingBase):
    pass


class MeetingUpdate(ORMModel):
    title: Optional[str] = None
    location: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    raw_notes: Optional[str] = None
    outcome: Optional[str] = None
    next_step: Optional[str] = None


class MeetingRead(MeetingBase, TimestampedRead):
    pass
