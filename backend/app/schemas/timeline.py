from datetime import datetime
from typing import Any, Literal, Optional

from app.schemas.base import ORMModel

TimelineItemType = Literal[
    "activity_event",
    "communication",
    "meeting",
    "note",
    "task",
]


class TimelineItem(ORMModel):
    item_type: TimelineItemType
    item_id: int
    occurred_at: datetime
    title: str
    summary: Optional[str] = None
    actor: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class TimelineResponse(ORMModel):
    investor_opportunity_id: int
    count: int
    items: list[TimelineItem]
