"""HTTP surface for the investor engine write-back system.

Endpoints:
    POST   /investor-engine/writes/request         — request approval for a write
    GET    /investor-engine/writes                  — list pending/failed writes
    GET    /investor-engine/writes/by-investor/{external_id}
    POST   /investor-engine/writes/worker/run       — drain pending batch
    POST   /investor-engine/writes/{id}/retrigger   — rerun a failed/pending write
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.integrations.investor_engine import worker, writes_service
from app.integrations.investor_engine.writes_models import (
    PendingEngineWrite,
    STATUS_FAILED,
    STATUS_PENDING,
    SUPPORTED_ACTIONS,
)
from app.integrations.investor_engine.writes_schemas import (
    PendingEngineWriteRead,
)
from app.models.approval import Approval
from app.schemas.approval import ApprovalRead

router = APIRouter()


class EngineWriteRequest(BaseModel):
    action_type: str
    payload: dict[str, Any]
    requested_by: Optional[str] = None
    note: Optional[str] = None


@router.post(
    "/writes/request/{external_id}",
    response_model=ApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
def request_write(
    external_id: str,
    payload: EngineWriteRequest,
    db: Session = Depends(get_db),
) -> ApprovalRead:
    if payload.action_type not in SUPPORTED_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported action_type: {payload.action_type!r}",
        )
    approval = writes_service.request_engine_write_approval(
        db,
        external_id=external_id,
        action_type=payload.action_type,
        payload=payload.payload,
        requested_by=payload.requested_by,
        note=payload.note,
    )
    return approval


@router.get("/writes", response_model=list[PendingEngineWriteRead])
def list_writes(
    status_filter: Optional[str] = Query(None, alias="status"),
    external_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PendingEngineWriteRead]:
    stmt = select(PendingEngineWrite)
    if status_filter:
        stmt = stmt.where(PendingEngineWrite.status == status_filter)
    if external_id:
        stmt = stmt.where(PendingEngineWrite.external_id == external_id)
    stmt = stmt.order_by(desc(PendingEngineWrite.created_at)).limit(limit)
    rows = list(db.execute(stmt).scalars().all())
    return [PendingEngineWriteRead.model_validate(r) for r in rows]


@router.get(
    "/writes/by-investor/{external_id}",
    response_model=list[PendingEngineWriteRead],
)
def list_writes_for_investor(
    external_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PendingEngineWriteRead]:
    stmt = (
        select(PendingEngineWrite)
        .where(PendingEngineWrite.external_id == external_id)
        .order_by(desc(PendingEngineWrite.created_at))
        .limit(limit)
    )
    rows = list(db.execute(stmt).scalars().all())
    return [PendingEngineWriteRead.model_validate(r) for r in rows]


@router.post("/writes/worker/run")
def run_worker(
    batch_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    report = worker.run_once(db, batch_size=batch_size)
    return report.as_dict()


@router.post(
    "/writes/{write_id}/retrigger", response_model=PendingEngineWriteRead
)
def retrigger_write(
    write_id: int,
    db: Session = Depends(get_db),
) -> PendingEngineWriteRead:
    row = worker.run_one(db, write_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Pending write not found")
    return PendingEngineWriteRead.model_validate(row)
