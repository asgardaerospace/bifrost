from typing import Optional

from app.schemas.base import ORMModel, TimestampedRead


class DocumentBase(ORMModel):
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    filename: str
    storage_path: str
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    summary: Optional[str] = None
    uploaded_by: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentRead(DocumentBase, TimestampedRead):
    pass
