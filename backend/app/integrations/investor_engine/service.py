"""Read surface over the investor engine snapshot cache.

Anything in Bifrost that wants to render engine-sourced investors goes
through this service. It returns `NormalizedInvestor` objects (defined
in the mapper), so callers never see the snapshot ORM model or the
raw engine payload.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.investor_engine.mapper import NormalizedInvestor
from app.integrations.investor_engine.models import InvestorEngineSnapshot


def _hydrate(snapshot: InvestorEngineSnapshot) -> NormalizedInvestor:
    return NormalizedInvestor.model_validate(snapshot.payload)


def list_investors(
    db: Session,
    *,
    stage: Optional[str] = None,
    follow_up_status: Optional[str] = None,
    owner: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[NormalizedInvestor]:
    stmt = select(InvestorEngineSnapshot)
    if stage:
        stmt = stmt.where(InvestorEngineSnapshot.stage == stage)
    if follow_up_status:
        stmt = stmt.where(
            InvestorEngineSnapshot.follow_up_status == follow_up_status
        )
    if owner:
        stmt = stmt.where(InvestorEngineSnapshot.owner == owner)
    stmt = stmt.order_by(InvestorEngineSnapshot.firm_name).offset(skip).limit(limit)
    return [_hydrate(s) for s in db.execute(stmt).scalars().all()]


def get_investor(db: Session, external_id: str) -> Optional[NormalizedInvestor]:
    snapshot = db.execute(
        select(InvestorEngineSnapshot).where(
            InvestorEngineSnapshot.external_id == external_id
        )
    ).scalar_one_or_none()
    return _hydrate(snapshot) if snapshot else None


def follow_ups_due(
    db: Session, *, as_of: Optional[datetime] = None, limit: int = 50
) -> list[NormalizedInvestor]:
    """Investors whose next follow-up is at or before `as_of`."""
    now = as_of or datetime.now(timezone.utc)
    stmt = (
        select(InvestorEngineSnapshot)
        .where(InvestorEngineSnapshot.next_follow_up_at.is_not(None))
        .where(InvestorEngineSnapshot.next_follow_up_at <= now)
        .order_by(InvestorEngineSnapshot.next_follow_up_at.asc())
        .limit(limit)
    )
    return [_hydrate(s) for s in db.execute(stmt).scalars().all()]


def dashboard_summary(db: Session) -> dict[str, int]:
    """Counts by stage + follow-up status for dashboard widgets."""
    rows = db.execute(
        select(InvestorEngineSnapshot.stage, InvestorEngineSnapshot.follow_up_status)
    ).all()
    by_stage: dict[str, int] = {}
    by_follow_up: dict[str, int] = {}
    for stage, follow_up in rows:
        if stage:
            by_stage[stage] = by_stage.get(stage, 0) + 1
        if follow_up:
            by_follow_up[follow_up] = by_follow_up.get(follow_up, 0) + 1
    return {
        "total": len(rows),
        **{f"stage.{k}": v for k, v in by_stage.items()},
        **{f"follow_up.{k}": v for k, v in by_follow_up.items()},
    }
