from typing import Optional

from app.schemas.base import ORMModel
from app.schemas.communication import CommunicationRead
from app.schemas.workflow import WorkflowRunRead


class FollowUpDraftRequest(ORMModel):
    contact_id: Optional[int] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    actor: Optional[str] = None


class FollowUpDraftResponse(ORMModel):
    communication: CommunicationRead
    workflow_run: WorkflowRunRead


class SendApprovalRequest(ORMModel):
    requested_by: Optional[str] = None
    note: Optional[str] = None
