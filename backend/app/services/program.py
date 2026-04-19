"""Program OS services — CRUD, pipeline summary, activity logging."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models.investor import InvestorFirm
from app.models.market import Account
from app.models.program import (
    Program,
    ProgramAccount,
    ProgramActivity,
    ProgramInvestor,
)
from app.schemas.program import (
    ProgramAccountCreate,
    ProgramActivityCreate,
    ProgramCreate,
    ProgramInvestorCreate,
    ProgramUpdate,
)
from app.services.activity import log_activity

ENTITY_PROGRAM = "program"
ENTITY_PROGRAM_ACCOUNT = "program_account"
ENTITY_PROGRAM_INVESTOR = "program_investor"
ENTITY_PROGRAM_ACTIVITY = "program_activity"

ACTIVE_STAGES = ("pursuing", "active")
HIGH_VALUE_THRESHOLD = 1_000_000.0
HIGH_VALUE_MIN_PROBABILITY = 50


def _not_found(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"{name} not found"
    )


def _assert_account(db: Session, account_id: int) -> Account:
    acct = db.get(Account, account_id)
    if acct is None or acct.deleted_at is not None:
        raise HTTPException(
            status_code=404, detail=f"Account #{account_id} not found"
        )
    return acct


# ---------------------------------------------------------------------------
# programs
# ---------------------------------------------------------------------------

def list_programs(
    db: Session,
    *,
    stage: Optional[str] = None,
    account_id: Optional[int] = None,
    owner: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Program]:
    stmt = select(Program).where(Program.deleted_at.is_(None))
    if stage:
        stmt = stmt.where(Program.stage == stage)
    if account_id is not None:
        stmt = stmt.where(Program.account_id == account_id)
    if owner:
        stmt = stmt.where(Program.owner == owner)
    stmt = stmt.order_by(desc(Program.updated_at)).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_active_programs(
    db: Session, *, limit: int = 100
) -> list[Program]:
    stmt = (
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(ACTIVE_STAGES))
        .order_by(desc(Program.updated_at))
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def list_high_value_programs(
    db: Session,
    *,
    threshold: float = HIGH_VALUE_THRESHOLD,
    limit: int = 50,
) -> list[Program]:
    stmt = (
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(ACTIVE_STAGES))
        .where(Program.estimated_value.is_not(None))
        .where(Program.estimated_value >= threshold)
        .order_by(desc(Program.estimated_value))
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def list_overdue_programs(
    db: Session, *, as_of: Optional[datetime] = None, limit: int = 100
) -> list[Program]:
    now = as_of or datetime.now(timezone.utc)
    stmt = (
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(ACTIVE_STAGES))
        .where(Program.next_step_due_at.is_not(None))
        .where(Program.next_step_due_at <= now)
        .order_by(Program.next_step_due_at.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_program(db: Session, program_id: int) -> Program:
    prog = db.get(Program, program_id)
    if prog is None or prog.deleted_at is not None:
        raise _not_found("Program")
    return prog


def create_program(
    db: Session, payload: ProgramCreate, *, actor: Optional[str] = None
) -> Program:
    _assert_account(db, payload.account_id)
    prog = Program(**payload.model_dump())
    db.add(prog)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_PROGRAM,
        entity_id=prog.id,
        event_type="program.created",
        summary=f"Program '{prog.name}' created (stage={prog.stage})",
        actor=actor,
        details={
            "account_id": prog.account_id,
            "stage": prog.stage,
            "estimated_value": float(prog.estimated_value)
            if prog.estimated_value is not None
            else None,
        },
    )
    db.commit()
    db.refresh(prog)
    return prog


def update_program(
    db: Session,
    program_id: int,
    payload: ProgramUpdate,
    *,
    actor: Optional[str] = None,
) -> Program:
    prog = get_program(db, program_id)
    changes = payload.model_dump(exclude_unset=True)
    if "account_id" in changes:
        _assert_account(db, changes["account_id"])

    prev_stage = prog.stage
    for k, v in changes.items():
        setattr(prog, k, v)
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_PROGRAM,
        entity_id=prog.id,
        event_type="program.updated",
        summary=f"Program '{prog.name}' updated",
        actor=actor,
        details={"changes": changes},
    )
    if "stage" in changes and changes["stage"] != prev_stage:
        log_activity(
            db,
            entity_type=ENTITY_PROGRAM,
            entity_id=prog.id,
            event_type="program.stage_changed",
            summary=(
                f"Program '{prog.name}' stage {prev_stage} → {prog.stage}"
            ),
            actor=actor,
            details={"from": prev_stage, "to": prog.stage},
        )
    db.commit()
    db.refresh(prog)
    return prog


# ---------------------------------------------------------------------------
# program <-> account links
# ---------------------------------------------------------------------------

def link_program_account(
    db: Session,
    payload: ProgramAccountCreate,
    *,
    actor: Optional[str] = None,
) -> ProgramAccount:
    get_program(db, payload.program_id)
    _assert_account(db, payload.account_id)
    existing = db.execute(
        select(ProgramAccount).where(
            and_(
                ProgramAccount.program_id == payload.program_id,
                ProgramAccount.account_id == payload.account_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account is already linked to this program",
        )
    link = ProgramAccount(**payload.model_dump())
    db.add(link)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_PROGRAM_ACCOUNT,
        entity_id=link.id,
        event_type="program_account.linked",
        summary=(
            f"Account #{link.account_id} linked to program #{link.program_id} as {link.role}"
        ),
        actor=actor,
        details={
            "program_id": link.program_id,
            "account_id": link.account_id,
            "role": link.role,
        },
    )
    db.commit()
    db.refresh(link)
    return link


def list_program_accounts(
    db: Session, program_id: int
) -> list[ProgramAccount]:
    get_program(db, program_id)
    stmt = select(ProgramAccount).where(ProgramAccount.program_id == program_id)
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# program <-> investor links
# ---------------------------------------------------------------------------

def link_program_investor(
    db: Session,
    payload: ProgramInvestorCreate,
    *,
    actor: Optional[str] = None,
) -> ProgramInvestor:
    get_program(db, payload.program_id)
    inv = db.get(InvestorFirm, payload.investor_id)
    if inv is None or inv.deleted_at is not None:
        raise HTTPException(
            status_code=404, detail=f"Investor #{payload.investor_id} not found"
        )
    existing = db.execute(
        select(ProgramInvestor).where(
            and_(
                ProgramInvestor.program_id == payload.program_id,
                ProgramInvestor.investor_id == payload.investor_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Investor is already linked to this program",
        )
    link = ProgramInvestor(**payload.model_dump())
    db.add(link)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_PROGRAM_INVESTOR,
        entity_id=link.id,
        event_type="program_investor.linked",
        summary=(
            f"Investor #{link.investor_id} linked to program #{link.program_id} ({link.relevance_type})"
        ),
        actor=actor,
        details={
            "program_id": link.program_id,
            "investor_id": link.investor_id,
            "relevance_type": link.relevance_type,
        },
    )
    db.commit()
    db.refresh(link)
    return link


def list_program_investors(
    db: Session, program_id: int
) -> list[ProgramInvestor]:
    get_program(db, program_id)
    stmt = select(ProgramInvestor).where(ProgramInvestor.program_id == program_id)
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# program activities (lightweight log table)
# ---------------------------------------------------------------------------

def create_program_activity(
    db: Session,
    payload: ProgramActivityCreate,
    *,
    actor: Optional[str] = None,
) -> ProgramActivity:
    get_program(db, payload.program_id)
    row = ProgramActivity(**payload.model_dump())
    db.add(row)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_PROGRAM,
        entity_id=payload.program_id,
        event_type=f"program.activity.{payload.activity_type}",
        summary=(
            payload.description
            or f"{payload.activity_type} recorded on program #{payload.program_id}"
        ),
        actor=actor,
        details={"program_activity_id": row.id},
    )
    db.commit()
    db.refresh(row)
    return row


def list_program_activities(
    db: Session, program_id: int, *, limit: int = 100
) -> list[ProgramActivity]:
    get_program(db, program_id)
    stmt = (
        select(ProgramActivity)
        .where(ProgramActivity.program_id == program_id)
        .order_by(desc(ProgramActivity.created_at))
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# pipeline summary
# ---------------------------------------------------------------------------

def pipeline_summary(
    db: Session, *, high_value_threshold: float = HIGH_VALUE_THRESHOLD
) -> dict:
    rows = db.execute(
        select(Program).where(Program.deleted_at.is_(None))
    ).scalars().all()

    by_stage: dict[str, int] = {}
    total_active_value = 0.0
    active_count = 0
    won_count = 0
    lost_count = 0
    for p in rows:
        by_stage[p.stage] = by_stage.get(p.stage, 0) + 1
        if p.stage in ACTIVE_STAGES:
            active_count += 1
            if p.estimated_value is not None:
                total_active_value += float(p.estimated_value)
        if p.stage == "won":
            won_count += 1
        if p.stage == "lost":
            lost_count += 1

    high_value = list_high_value_programs(
        db, threshold=high_value_threshold, limit=10
    )
    overdue = list_overdue_programs(db, limit=10)

    return {
        "total_programs": len(rows),
        "active_count": active_count,
        "won_count": won_count,
        "lost_count": lost_count,
        "stage_counts": [
            {"stage": k, "count": v} for k, v in sorted(by_stage.items())
        ],
        "high_value_count": len(high_value),
        "high_value_threshold": high_value_threshold,
        "overdue_count": len(overdue),
        "total_estimated_value_active": total_active_value,
        "high_value": high_value,
        "overdue": overdue,
    }
