from datetime import datetime
from typing import Optional

from app.schemas.base import ORMModel, TimestampedRead


class ApprovalBase(ORMModel):
    entity_type: str
    entity_id: int
    workflow_run_id: Optional[int] = None
    action: str
    status: str = "pending"
    requested_by: Optional[str] = None


class ApprovalCreate(ApprovalBase):
    pass


class ApprovalDecision(ORMModel):
    status: str
    reviewer: str
    reviewed_at: datetime
    decision_note: Optional[str] = None


class ApprovalDecisionInput(ORMModel):
    reviewer: str
    decision_note: Optional[str] = None


class ApprovalRead(ApprovalBase, TimestampedRead):
    reviewer: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    # Populated when the approval's entity is a communication. Lets the
    # UI render subject + source badge without an N+1 fetch.
    communication_subject: Optional[str] = None
    communication_status: Optional[str] = None
    source_system: Optional[str] = None
    source_external_id: Optional[str] = None
