from datetime import datetime
from typing import Any, Optional

from app.schemas.base import ORMModel


class ActivityEventBase(ORMModel):
    entity_type: str
    entity_id: int
    event_type: str
    actor: Optional[str] = None
    source: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class ActivityEventCreate(ActivityEventBase):
    pass


class ActivityEventRead(ActivityEventBase):
    id: int
    created_at: datetime
