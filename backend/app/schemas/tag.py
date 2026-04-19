from datetime import datetime
from typing import Optional

from app.schemas.base import ORMModel, TimestampedRead


class TagBase(ORMModel):
    name: str
    color: Optional[str] = None


class TagCreate(TagBase):
    pass


class TagRead(TagBase, TimestampedRead):
    pass


class EntityTagCreate(ORMModel):
    tag_id: int
    entity_type: str
    entity_id: int


class EntityTagRead(ORMModel):
    tag_id: int
    entity_type: str
    entity_id: int
    created_at: datetime
