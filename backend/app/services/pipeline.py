from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity import ActivityEvent
from app.models.communication import Communication
from app.models.investor import InvestorFirm, InvestorOpportunity
from app.models.meeting import Meeting
from app.schemas.pipeline import (
    OpportunitySummary,
    PipelineSummary,
    StageCount,
)

ENTITY_OPPORTUNITY = "investor_opportunity"

CLOSED_STAGES = {"closed_won", "closed_lost", "deferred"}
CLOSED_STATUSES = {"closed_won", "closed_lost", "deferred", "closed"}

STAGE_WEIGHTS = {
    "prospect": 5,
    "identified": 10,
    "qualified": 20,
    "contacted": 30,
    "intro_call": 45,
    "diligence": 60,
    "partner_meeting": 80,
    "term_sheet": 95,
    "decision": 90,
}

DEFAULT_STALE_DAYS = 21
DEFAULT_TOP_PRIORITY = 10


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_active(opp: InvestorOpportunity) -> bool:
    if opp.deleted_at is not None:
        return False
    if (opp.stage or "").lower() in CLOSED_STAGES:
        return False
    if (opp.status or "").lower() in CLOSED_STATUSES:
        return False
    return True


def _active_stmt():
    return (
        select(InvestorOpportunity)
        .where(InvestorOpportunity.deleted_at.is_(None))
        .where(func.lower(InvestorOpportunity.stage).not_in(CLOSED_STAGES))
        .where(func.lower(InvestorOpportunity.status).not_in(CLOSED_STATUSES))
    )


def _last_interaction_map(
    db: Session, opportunity_ids: list[int]
) -> dict[int, datetime]:
    """
    Compute last_interaction_at for each opportunity as the max of:
      - activity_events.created_at (entity_type=investor_opportunity)
      - communications.sent_at (entity_type=investor_opportunity)
      - meetings.starts_at (entity_type=investor_opportunity)

    Rationale: data_model.md requires every activity-producing action to
    create an ActivityEvent, so activity_events is authoritative. We also
    fold in sent communications and scheduled meetings as explicit signals.
    """
    if not opportunity_ids:
        return {}

    result: dict[int, datetime] = {}

    def _merge(rows):
        for entity_id, ts in rows:
            if ts is None:
                continue
            current = result.get(entity_id)
            if current is None or ts > current:
                result[entity_id] = ts

    act_rows = db.execute(
        select(ActivityEvent.entity_id, func.max(ActivityEvent.created_at))
        .where(ActivityEvent.entity_type == ENTITY_OPPORTUNITY)
        .where(ActivityEvent.entity_id.in_(opportunity_ids))
        .group_by(ActivityEvent.entity_id)
    ).all()
    _merge(act_rows)

    comm_rows = db.execute(
        select(Communication.entity_id, func.max(Communication.sent_at))
        .where(Communication.entity_type == ENTITY_OPPORTUNITY)
        .where(Communication.entity_id.in_(opportunity_ids))
        .where(Communication.sent_at.is_not(None))
        .group_by(Communication.entity_id)
    ).all()
    _merge(comm_rows)

    meet_rows = db.execute(
        select(Meeting.entity_id, func.max(Meeting.starts_at))
        .where(Meeting.entity_type == ENTITY_OPPORTUNITY)
        .where(Meeting.entity_id.in_(opportunity_ids))
        .group_by(Meeting.entity_id)
    ).all()
    _merge(meet_rows)

    return result


def _firm_name_map(
    db: Session, firm_ids: list[int]
) -> dict[int, str]:
    if not firm_ids:
        return {}
    rows = db.execute(
        select(InvestorFirm.id, InvestorFirm.name).where(InvestorFirm.id.in_(firm_ids))
    ).all()
    return {fid: name for fid, name in rows}


def _priority_score(
    opp: InvestorOpportunity,
    last_interaction_at: Optional[datetime],
    now: datetime,
) -> float:
    stage_weight = STAGE_WEIGHTS.get((opp.stage or "").lower(), 0)

    def _clip(v):
        return max(0, min(100, int(v))) if v is not None else 0

    scoring = (
        _clip(opp.probability_score) * 0.4
        + _clip(opp.strategic_value_score) * 0.4
        + _clip(opp.fit_score) * 0.2
    )

    overdue_bonus = 0.0
    if opp.next_step_due_at is not None and opp.next_step_due_at < now:
        days_overdue = (now - opp.next_step_due_at).days
        overdue_bonus = min(25.0, float(days_overdue) * 2.0)

    stale_penalty = 0.0
    if last_interaction_at is not None:
        days_since = (now - last_interaction_at).days
        if days_since > DEFAULT_STALE_DAYS:
            stale_penalty = min(20.0, float(days_since - DEFAULT_STALE_DAYS))

    return round(stage_weight + scoring + overdue_bonus - stale_penalty, 2)


def _to_summary(
    opp: InvestorOpportunity,
    firm_names: dict[int, str],
    last_interactions: dict[int, datetime],
    now: datetime,
) -> OpportunitySummary:
    last = last_interactions.get(opp.id)
    days_since = (now - last).days if last is not None else None
    return OpportunitySummary(
        id=opp.id,
        firm_id=opp.firm_id,
        firm_name=firm_names.get(opp.firm_id),
        stage=opp.stage,
        status=opp.status,
        owner=opp.owner,
        next_step=opp.next_step,
        next_step_due_at=opp.next_step_due_at,
        fit_score=opp.fit_score,
        probability_score=opp.probability_score,
        strategic_value_score=opp.strategic_value_score,
        last_interaction_at=last,
        days_since_last_interaction=days_since,
        priority_score=_priority_score(opp, last, now),
    )


# ---------------------------------------------------------------------------
# queries
# ---------------------------------------------------------------------------

def list_active_opportunities(db: Session) -> list[InvestorOpportunity]:
    return list(db.scalars(_active_stmt()).all())


def list_overdue_follow_ups(db: Session) -> list[InvestorOpportunity]:
    now = _now()
    stmt = (
        _active_stmt()
        .where(InvestorOpportunity.next_step_due_at.is_not(None))
        .where(InvestorOpportunity.next_step_due_at < now)
        .order_by(InvestorOpportunity.next_step_due_at.asc())
    )
    return list(db.scalars(stmt).all())


def list_missing_next_step(db: Session) -> list[InvestorOpportunity]:
    stmt = _active_stmt().where(
        (InvestorOpportunity.next_step.is_(None))
        | (func.length(func.trim(InvestorOpportunity.next_step)) == 0)
    )
    return list(db.scalars(stmt).all())


def list_stale_opportunities(
    db: Session, *, threshold_days: int = DEFAULT_STALE_DAYS
) -> list[tuple[InvestorOpportunity, Optional[datetime]]]:
    now = _now()
    cutoff = now - timedelta(days=threshold_days)

    opps = list_active_opportunities(db)
    interactions = _last_interaction_map(db, [o.id for o in opps])

    stale: list[tuple[InvestorOpportunity, Optional[datetime]]] = []
    for opp in opps:
        last = interactions.get(opp.id)
        if last is None or last < cutoff:
            stale.append((opp, last))
    stale.sort(
        key=lambda item: item[1] or datetime.min.replace(tzinfo=timezone.utc)
    )
    return stale


def count_by_stage(db: Session) -> list[StageCount]:
    rows = db.execute(
        _active_stmt()
        .with_only_columns(InvestorOpportunity.stage, func.count())
        .group_by(InvestorOpportunity.stage)
        .order_by(InvestorOpportunity.stage.asc())
    ).all()
    return [StageCount(stage=stage or "unknown", count=count) for stage, count in rows]


def build_pipeline_summary(
    db: Session,
    *,
    stale_threshold_days: int = DEFAULT_STALE_DAYS,
    top_priority_limit: int = DEFAULT_TOP_PRIORITY,
) -> PipelineSummary:
    now = _now()
    cutoff = now - timedelta(days=stale_threshold_days)

    active = list_active_opportunities(db)
    opp_ids = [o.id for o in active]
    firm_names = _firm_name_map(db, [o.firm_id for o in active])
    interactions = _last_interaction_map(db, opp_ids)

    stage_counts = count_by_stage(db)

    summaries = [
        _to_summary(opp, firm_names, interactions, now) for opp in active
    ]

    missing_next_step = [s for s in summaries if not (s.next_step and s.next_step.strip())]
    overdue = [
        s for s in summaries
        if s.next_step_due_at is not None and s.next_step_due_at < now
    ]
    overdue.sort(key=lambda s: s.next_step_due_at or now)

    stale = [
        s for s in summaries
        if s.last_interaction_at is None or s.last_interaction_at < cutoff
    ]
    stale.sort(
        key=lambda s: s.last_interaction_at or datetime.min.replace(tzinfo=timezone.utc)
    )

    top = sorted(
        summaries, key=lambda s: s.priority_score or 0.0, reverse=True
    )[:top_priority_limit]

    return PipelineSummary(
        total_active=len(active),
        stage_counts=stage_counts,
        missing_next_step_count=len(missing_next_step),
        overdue_follow_up_count=len(overdue),
        stale_count=len(stale),
        stale_threshold_days=stale_threshold_days,
        top_priority=top,
        overdue_follow_ups=overdue,
        stale_opportunities=stale,
    )


def list_overdue_summaries(db: Session) -> list[OpportunitySummary]:
    now = _now()
    opps = list_overdue_follow_ups(db)
    firm_names = _firm_name_map(db, [o.firm_id for o in opps])
    interactions = _last_interaction_map(db, [o.id for o in opps])
    return [_to_summary(o, firm_names, interactions, now) for o in opps]


def list_stale_summaries(
    db: Session, *, threshold_days: int = DEFAULT_STALE_DAYS
) -> list[OpportunitySummary]:
    now = _now()
    pairs = list_stale_opportunities(db, threshold_days=threshold_days)
    opps = [p[0] for p in pairs]
    firm_names = _firm_name_map(db, [o.firm_id for o in opps])
    interactions = {o.id: last for (o, last) in pairs if last is not None}
    return [_to_summary(o, firm_names, interactions, now) for o in opps]
