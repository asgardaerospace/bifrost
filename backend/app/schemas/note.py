from typing import Optional

from app.schemas.base import ORMModel, TimestampedRead


class NoteBase(ORMModel):
    entity_type: str
    entity_id: int
    author: Optional[str] = None
    body: str


class NoteCreate(NoteBase):
    pass


class NoteUpdate(ORMModel):
    body: Optional[str] = None


class NoteRead(NoteBase, TimestampedRead):
    pass
