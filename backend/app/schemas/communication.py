from datetime import datetime
from typing import Optional

from app.schemas.base import ORMModel, TimestampedRead


class CommunicationBase(ORMModel):
    entity_type: str
    entity_id: int
    channel: str
    direction: str
    status: str = "draft"
    subject: Optional[str] = None
    body: Optional[str] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    sent_at: Optional[datetime] = None
    source_system: Optional[str] = None
    source_external_id: Optional[str] = None


class CommunicationCreate(CommunicationBase):
    pass


class CommunicationUpdate(ORMModel):
    status: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    sent_at: Optional[datetime] = None


class CommunicationRead(CommunicationBase, TimestampedRead):
    pass
