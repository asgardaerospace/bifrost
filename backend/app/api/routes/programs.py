"""HTTP endpoints for Program OS."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.investor import InvestorFirm
from app.models.market import Account
from app.schemas.program import (
    ProgramAccountCreate,
    ProgramAccountRead,
    ProgramActivityCreate,
    ProgramActivityRead,
    ProgramCreate,
    ProgramInvestorCreate,
    ProgramInvestorRead,
    ProgramPipelineSummary,
    ProgramRead,
    ProgramStageCount,
    ProgramUpdate,
)
from app.services import program as program_service

router = APIRouter()


def _hydrate(db: Session, prog) -> ProgramRead:
    account_name: Optional[str] = None
    if prog.account_id:
        acct = db.get(Account, prog.account_id)
        account_name = acct.name if acct else None
    return ProgramRead.model_validate(prog).model_copy(
        update={"account_name": account_name}
    )


def _hydrate_many(db: Session, rows) -> list[ProgramRead]:
    if not rows:
        return []
    ids = {p.account_id for p in rows if p.account_id}
    accounts = {}
    if ids:
        from sqlalchemy import select
        stmt = select(Account).where(Account.id.in_(ids))
        accounts = {a.id: a.name for a in db.execute(stmt).scalars().all()}
    return [
        ProgramRead.model_validate(p).model_copy(
            update={"account_name": accounts.get(p.account_id)}
        )
        for p in rows
    ]


# --- programs ----------------------------------------------------------------


@router.get("/programs", response_model=list[ProgramRead])
def list_programs(
    stage: Optional[str] = None,
    account_id: Optional[int] = None,
    owner: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ProgramRead]:
    rows = program_service.list_programs(
        db, stage=stage, account_id=account_id, owner=owner, skip=skip, limit=limit
    )
    return _hydrate_many(db, rows)


@router.get("/programs/active", response_model=list[ProgramRead])
def list_active(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ProgramRead]:
    return _hydrate_many(db, program_service.list_active_programs(db, limit=limit))


@router.get("/programs/high-value", response_model=list[ProgramRead])
def list_high_value(
    threshold: float = Query(
        program_service.HIGH_VALUE_THRESHOLD, ge=0
    ),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[ProgramRead]:
    return _hydrate_many(
        db, program_service.list_high_value_programs(db, threshold=threshold, limit=limit)
    )


@router.get("/programs/overdue", response_model=list[ProgramRead])
def list_overdue(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ProgramRead]:
    return _hydrate_many(db, program_service.list_overdue_programs(db, limit=limit))


@router.get("/programs/pipeline-summary", response_model=ProgramPipelineSummary)
def pipeline_summary(
    high_value_threshold: float = Query(
        program_service.HIGH_VALUE_THRESHOLD, ge=0
    ),
    db: Session = Depends(get_db),
) -> ProgramPipelineSummary:
    data = program_service.pipeline_summary(
        db, high_value_threshold=high_value_threshold
    )
    return ProgramPipelineSummary(
        total_programs=data["total_programs"],
        active_count=data["active_count"],
        won_count=data["won_count"],
        lost_count=data["lost_count"],
        stage_counts=[ProgramStageCount(**s) for s in data["stage_counts"]],
        high_value_count=data["high_value_count"],
        high_value_threshold=data["high_value_threshold"],
        overdue_count=data["overdue_count"],
        total_estimated_value_active=data["total_estimated_value_active"],
        high_value=_hydrate_many(db, data["high_value"]),
        overdue=_hydrate_many(db, data["overdue"]),
    )


@router.get("/programs/{program_id}", response_model=ProgramRead)
def get_program(program_id: int, db: Session = Depends(get_db)) -> ProgramRead:
    return _hydrate(db, program_service.get_program(db, program_id))


@router.post(
    "/programs", response_model=ProgramRead, status_code=status.HTTP_201_CREATED
)
def create_program(
    payload: ProgramCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> ProgramRead:
    return _hydrate(db, program_service.create_program(db, payload, actor=actor))


@router.patch("/programs/{program_id}", response_model=ProgramRead)
def update_program(
    program_id: int,
    payload: ProgramUpdate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> ProgramRead:
    return _hydrate(
        db, program_service.update_program(db, program_id, payload, actor=actor)
    )


# --- program <-> account links -----------------------------------------------


@router.post(
    "/program-accounts",
    response_model=ProgramAccountRead,
    status_code=status.HTTP_201_CREATED,
)
def link_program_account(
    payload: ProgramAccountCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> ProgramAccountRead:
    link = program_service.link_program_account(db, payload, actor=actor)
    acct = db.get(Account, link.account_id)
    return ProgramAccountRead.model_validate(link).model_copy(
        update={"account_name": acct.name if acct else None}
    )


@router.get(
    "/programs/{program_id}/accounts",
    response_model=list[ProgramAccountRead],
)
def list_program_accounts(
    program_id: int, db: Session = Depends(get_db)
) -> list[ProgramAccountRead]:
    rows = program_service.list_program_accounts(db, program_id)
    result = []
    for l in rows:
        acct = db.get(Account, l.account_id)
        result.append(
            ProgramAccountRead.model_validate(l).model_copy(
                update={"account_name": acct.name if acct else None}
            )
        )
    return result


# --- program <-> investor links ----------------------------------------------


@router.post(
    "/program-investors",
    response_model=ProgramInvestorRead,
    status_code=status.HTTP_201_CREATED,
)
def link_program_investor(
    payload: ProgramInvestorCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> ProgramInvestorRead:
    link = program_service.link_program_investor(db, payload, actor=actor)
    inv = db.get(InvestorFirm, link.investor_id)
    return ProgramInvestorRead.model_validate(link).model_copy(
        update={"investor_name": inv.name if inv else None}
    )


@router.get(
    "/programs/{program_id}/investors",
    response_model=list[ProgramInvestorRead],
)
def list_program_investors(
    program_id: int, db: Session = Depends(get_db)
) -> list[ProgramInvestorRead]:
    rows = program_service.list_program_investors(db, program_id)
    result = []
    for l in rows:
        inv = db.get(InvestorFirm, l.investor_id)
        result.append(
            ProgramInvestorRead.model_validate(l).model_copy(
                update={"investor_name": inv.name if inv else None}
            )
        )
    return result


# --- program activities ------------------------------------------------------


@router.post(
    "/program-activities",
    response_model=ProgramActivityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_program_activity(
    payload: ProgramActivityCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> ProgramActivityRead:
    return ProgramActivityRead.model_validate(
        program_service.create_program_activity(db, payload, actor=actor)
    )


@router.get(
    "/programs/{program_id}/activities",
    response_model=list[ProgramActivityRead],
)
def list_program_activities(
    program_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ProgramActivityRead]:
    rows = program_service.list_program_activities(db, program_id, limit=limit)
    return [ProgramActivityRead.model_validate(r) for r in rows]
