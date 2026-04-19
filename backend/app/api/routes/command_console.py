from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.command_console import (
    CommandHistoryItem,
    CommandRequest,
    CommandResponse,
)
from app.services import command_executor, command_history

router = APIRouter()


@router.post("/commands", response_model=CommandResponse)
def submit_command(
    payload: CommandRequest, db: Session = Depends(get_db)
) -> CommandResponse:
    return command_executor.execute(db, payload)


@router.get("/history", response_model=list[CommandHistoryItem])
def list_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[CommandHistoryItem]:
    return command_history.list_history(db, skip=skip, limit=limit)
