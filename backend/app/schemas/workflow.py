from datetime import datetime
from typing import Any, Optional

from app.schemas.base import ORMModel, TimestampedRead


class WorkflowRunBase(ORMModel):
    workflow_key: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    status: str = "pending"
    triggered_by: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_payload: Optional[dict[str, Any]] = None
    result_payload: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None


class WorkflowRunCreate(WorkflowRunBase):
    pass


class WorkflowRunRead(WorkflowRunBase, TimestampedRead):
    pass
