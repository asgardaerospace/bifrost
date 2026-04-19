from datetime import datetime
from typing import Optional

from app.schemas.base import ORMModel, TimestampedRead


class TaskBase(ORMModel):
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: str = "open"
    priority: Optional[str] = None
    assignee: Optional[str] = None
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(ORMModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskRead(TaskBase, TimestampedRead):
    pass
