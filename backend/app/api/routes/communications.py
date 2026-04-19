from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.approval import ApprovalRead
from app.schemas.workflows import SendApprovalRequest
from app.services import communications as communications_service

router = APIRouter()


@router.get("/")
def list_communications() -> list:
    return []


@router.post(
    "/{communication_id}/request-send-approval",
    response_model=ApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
def request_send_approval(
    communication_id: int,
    payload: SendApprovalRequest,
    db: Session = Depends(get_db),
) -> ApprovalRead:
    approval = communications_service.request_send_approval(
        db,
        communication_id,
        requested_by=payload.requested_by,
        note=payload.note,
    )
    return approval
