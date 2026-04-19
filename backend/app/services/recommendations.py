"""Graph-level recommendation engine.

Consumes ``app.services.graph`` relationship matches and emits structured
``Recommendation`` objects with deterministic confidence scores. Every
recommendation ties back to named entities so the caller (Executive OS
briefing, Command Console, graph API) can render click-through links.

Scoring is rule-based — no ML. ``confidence_score`` is derived from the
underlying graph match scores and program fundamentals; callers should
treat it as a heuristic prioritization signal, not a probability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market import Account, MarketOpportunity
from app.models.program import Program, ProgramInvestor
from app.models.supplier import ProgramSupplier
from app.schemas.graph import (
    GraphEntity,
    Recommendation,
    RecommendationBundle,
)
from app.services import graph as graph_service

# --- tuning -----------------------------------------------------------------

MIN_INVESTOR_SCORE = 40
MIN_SUPPLIER_SCORE = 40
MIN_ACCOUNT_SCORE = 40
TOP_N_PER_PROGRAM = 3
ACTIVE_STAGES = ("pursuing", "active")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clip(v: float) -> int:
    return max(0, min(100, int(round(v))))


# ---------------------------------------------------------------------------
# investor recommendations for each active program
# ---------------------------------------------------------------------------


def _recs_investors_for_programs(db: Session) -> list[Recommendation]:
    programs = db.execute(
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(ACTIVE_STAGES))
    ).scalars().all()

    out: list[Recommendation] = []
    for prog in programs:
        matches = graph_service.match_investors_for_program(
            db, prog.id, limit=TOP_N_PER_PROGRAM * 2
        )
        fresh = [m for m in matches.matches if not m.already_linked]
        for m in fresh[:TOP_N_PER_PROGRAM]:
            if m.score < MIN_INVESTOR_SCORE:
                continue
            out.append(
                Recommendation(
                    id=f"rec.investor_for_program.{prog.id}.{m.investor_id}",
                    type="investor_for_program",
                    headline=(
                        f"Engage {m.investor_name} for program '{prog.name}'"
                    ),
                    reasoning=(
                        f"Match score {m.score}. "
                        + "; ".join(m.factors)
                    ),
                    confidence_score=m.score,
                    recommended_action=(
                        f"Open a capital conversation with {m.investor_name} "
                        f"and link as a program investor."
                    ),
                    related_entities=[
                        GraphEntity(type="program", id=prog.id, name=prog.name),
                        GraphEntity(
                            type="investor_firm",
                            id=m.investor_id,
                            name=m.investor_name,
                        ),
                    ],
                    link_hint=f"/graph/program/{prog.id}/investors",
                )
            )
    return out


# ---------------------------------------------------------------------------
# supplier recommendations for each active program
# ---------------------------------------------------------------------------


def _recs_suppliers_for_programs(db: Session) -> list[Recommendation]:
    programs = db.execute(
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(ACTIVE_STAGES))
    ).scalars().all()

    out: list[Recommendation] = []
    for prog in programs:
        matches = graph_service.match_suppliers_for_program(
            db, prog.id, limit=TOP_N_PER_PROGRAM * 2
        )
        fresh = [m for m in matches.matches if not m.already_linked]
        for m in fresh[:TOP_N_PER_PROGRAM]:
            if m.score < MIN_SUPPLIER_SCORE:
                continue
            out.append(
                Recommendation(
                    id=f"rec.supplier_for_program.{prog.id}.{m.supplier_id}",
                    type="supplier_for_program",
                    headline=(
                        f"Assign {m.supplier_name} to program '{prog.name}'"
                    ),
                    reasoning=(
                        f"Match score {m.score}. "
                        + "; ".join(m.factors)
                    ),
                    confidence_score=m.score,
                    recommended_action=(
                        f"Link {m.supplier_name} to program {prog.name} via "
                        "/program-suppliers and confirm role/status."
                    ),
                    related_entities=[
                        GraphEntity(type="program", id=prog.id, name=prog.name),
                        GraphEntity(
                            type="supplier",
                            id=m.supplier_id,
                            name=m.supplier_name,
                        ),
                    ],
                    link_hint=f"/graph/program/{prog.id}/suppliers",
                )
            )
    return out


# ---------------------------------------------------------------------------
# accounts to pursue, based on active program patterns
# ---------------------------------------------------------------------------


def _recs_accounts_to_pursue(db: Session) -> list[Recommendation]:
    """Suggest accounts whose sector matches active program sectors but
    who are not yet linked to any active program.
    """
    active_programs = db.execute(
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(ACTIVE_STAGES))
    ).scalars().all()
    if not active_programs:
        return []

    program_account_ids = {p.account_id for p in active_programs if p.account_id}
    if not program_account_ids:
        return []
    active_accounts = db.execute(
        select(Account).where(Account.id.in_(program_account_ids))
    ).scalars().all()
    active_sectors = {
        (a.sector or "").lower() for a in active_accounts if a.sector
    }
    active_sectors.discard("")
    if not active_sectors:
        return []

    candidates = db.execute(
        select(Account)
        .where(Account.deleted_at.is_(None))
        .where(Account.id.notin_(program_account_ids))
    ).scalars().all()

    # candidates must have an active market opportunity to be worth
    # pursuing — otherwise there's no inbound signal.
    with_open_opps = {
        row.account_id
        for row in db.execute(
            select(MarketOpportunity)
            .where(MarketOpportunity.deleted_at.is_(None))
            .where(MarketOpportunity.stage.in_(("exploring", "active")))
        ).scalars().all()
    }

    out: list[Recommendation] = []
    for a in candidates:
        if a.id not in with_open_opps:
            continue
        if not a.sector or a.sector.lower() not in active_sectors:
            continue
        # confidence: 50 baseline + 25 if region also matches any active
        # program's region, capped at 100.
        score = 50
        factors = [f"sector '{a.sector}' matches active program sectors"]
        active_regions = {
            (acct.region or "").lower() for acct in active_accounts if acct.region
        }
        if a.region and a.region.lower() in active_regions:
            score += 25
            factors.append(f"region '{a.region}' matches active program regions")
        out.append(
            Recommendation(
                id=f"rec.account_to_pursue.{a.id}",
                type="account_to_pursue",
                headline=f"Pursue account {a.name}",
                reasoning=(
                    f"Confidence {score}. " + "; ".join(factors) + "."
                ),
                confidence_score=_clip(score),
                recommended_action=(
                    f"Run a market campaign targeting {a.name}; connect open "
                    "opportunity to a program if fit emerges."
                ),
                related_entities=[
                    GraphEntity(type="account", id=a.id, name=a.name),
                ],
                link_hint="/market",
            )
        )
    return out


# ---------------------------------------------------------------------------
# risk-style recommendations
# ---------------------------------------------------------------------------


def _recs_programs_at_risk_no_supplier(db: Session) -> list[Recommendation]:
    programs = db.execute(
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(ACTIVE_STAGES))
    ).scalars().all()
    if not programs:
        return []
    linked_ids = {
        row.program_id
        for row in db.execute(
            select(ProgramSupplier).where(
                ProgramSupplier.program_id.in_([p.id for p in programs])
            )
        ).scalars().all()
    }
    out: list[Recommendation] = []
    for p in programs:
        if p.id in linked_ids:
            continue
        high_value = (
            p.estimated_value is not None
            and float(p.estimated_value) >= graph_service.HIGH_VALUE_THRESHOLD
        )
        score = 80 if high_value else 65
        out.append(
            Recommendation(
                id=f"rec.program_at_risk_no_supplier.{p.id}",
                type="program_at_risk_no_supplier",
                headline=f"Program '{p.name}' has no suppliers linked",
                reasoning=(
                    f"Program in stage {p.stage} with "
                    + ("high" if high_value else "unstated")
                    + " estimated value has zero program_suppliers rows — "
                    "delivery capacity is unassigned."
                ),
                confidence_score=score,
                recommended_action=(
                    "Review /graph/program/{id}/suppliers and assign the "
                    "top-ranked qualified supplier(s)."
                ),
                related_entities=[
                    GraphEntity(type="program", id=p.id, name=p.name),
                ],
                link_hint=f"/graph/program/{p.id}/suppliers",
            )
        )
    return out


def _recs_programs_at_risk_no_investor(db: Session) -> list[Recommendation]:
    programs = db.execute(
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(ACTIVE_STAGES))
        .where(Program.estimated_value.is_not(None))
        .where(Program.estimated_value >= graph_service.HIGH_VALUE_THRESHOLD)
    ).scalars().all()
    if not programs:
        return []
    linked_ids = {
        row.program_id
        for row in db.execute(
            select(ProgramInvestor).where(
                ProgramInvestor.program_id.in_([p.id for p in programs])
            )
        ).scalars().all()
    }
    out: list[Recommendation] = []
    for p in programs:
        if p.id in linked_ids:
            continue
        out.append(
            Recommendation(
                id=f"rec.program_at_risk_no_investor.{p.id}",
                type="program_at_risk_no_investor",
                headline=(
                    f"High-value program '{p.name}' has no investor coverage"
                ),
                reasoning=(
                    f"Program has estimated_value ≥ "
                    f"{graph_service.HIGH_VALUE_THRESHOLD:,.0f} but no "
                    "program_investors link exists."
                ),
                confidence_score=70,
                recommended_action=(
                    "Use /graph/program/{id}/investors and engage the top "
                    "match for strategic/funding relevance."
                ),
                related_entities=[
                    GraphEntity(type="program", id=p.id, name=p.name),
                ],
                link_hint=f"/graph/program/{p.id}/investors",
            )
        )
    return out


# ---------------------------------------------------------------------------
# cross-domain opportunity — active investor + active market opp + active program
# in the same sector.
# ---------------------------------------------------------------------------


def _recs_cross_domain_opportunities(db: Session) -> list[Recommendation]:
    programs = db.execute(
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(ACTIVE_STAGES))
    ).scalars().all()
    if not programs:
        return []
    account_ids = {p.account_id for p in programs if p.account_id}
    accounts = (
        db.execute(
            select(Account).where(Account.id.in_(account_ids))
        ).scalars().all()
        if account_ids
        else []
    )
    accounts_by_id = {a.id: a for a in accounts}

    open_opps_by_sector: dict[str, list[MarketOpportunity]] = {}
    opps = db.execute(
        select(MarketOpportunity, Account)
        .join(Account, Account.id == MarketOpportunity.account_id)
        .where(MarketOpportunity.deleted_at.is_(None))
        .where(MarketOpportunity.stage.in_(("exploring", "active")))
    ).all()
    for opp, acct in opps:
        if not acct.sector:
            continue
        open_opps_by_sector.setdefault(acct.sector.lower(), []).append(opp)

    out: list[Recommendation] = []
    for p in programs:
        acct = accounts_by_id.get(p.account_id) if p.account_id else None
        if acct is None or not acct.sector:
            continue
        sector_key = acct.sector.lower()
        related_opps = [
            o for o in open_opps_by_sector.get(sector_key, [])
            if o.account_id != p.account_id
        ]
        if not related_opps:
            continue
        investor_matches = graph_service.match_investors_for_program(
            db, p.id, limit=1
        ).matches
        top_investor = investor_matches[0] if investor_matches else None
        score = 55
        factors = [
            f"active program '{p.name}' in sector {acct.sector}",
            f"{len(related_opps)} open market opportunit(ies) in same sector",
        ]
        if top_investor and top_investor.score >= MIN_INVESTOR_SCORE:
            score += 20
            factors.append(
                f"top investor match: {top_investor.investor_name} "
                f"(score {top_investor.score})"
            )
        entities = [GraphEntity(type="program", id=p.id, name=p.name)]
        for o in related_opps[:2]:
            other_acct = db.get(Account, o.account_id)
            if other_acct:
                entities.append(
                    GraphEntity(
                        type="account", id=other_acct.id, name=other_acct.name
                    )
                )
        if top_investor:
            entities.append(
                GraphEntity(
                    type="investor_firm",
                    id=top_investor.investor_id,
                    name=top_investor.investor_name,
                )
            )

        out.append(
            Recommendation(
                id=f"rec.cross_domain.{p.id}",
                type="cross_domain_opportunity",
                headline=(
                    f"Cross-domain play around program '{p.name}' "
                    f"({acct.sector})"
                ),
                reasoning="; ".join(factors) + ".",
                confidence_score=_clip(score),
                recommended_action=(
                    "Package the program narrative with the related market "
                    "opportunities and brief the top-matched investor."
                ),
                related_entities=entities,
                link_hint=f"/graph/program/{p.id}/investors",
            )
        )
    return out


# ---------------------------------------------------------------------------
# top-level bundle
# ---------------------------------------------------------------------------


_REC_BUILDERS = (
    _recs_investors_for_programs,
    _recs_suppliers_for_programs,
    _recs_accounts_to_pursue,
    _recs_programs_at_risk_no_supplier,
    _recs_programs_at_risk_no_investor,
    _recs_cross_domain_opportunities,
)


def build_recommendations(
    db: Session,
    *,
    types: Optional[Iterable[str]] = None,
    limit: int = 100,
) -> RecommendationBundle:
    """Aggregate all recommendation producers, sort by confidence."""
    wanted = set(types) if types else None
    collected: list[Recommendation] = []
    for builder in _REC_BUILDERS:
        for rec in builder(db):
            if wanted and rec.type not in wanted:
                continue
            collected.append(rec)

    collected.sort(key=lambda r: (-r.confidence_score, r.type, r.id))

    counts: dict[str, int] = {}
    for r in collected:
        counts[r.type] = counts.get(r.type, 0) + 1

    return RecommendationBundle(
        generated_at=_now(),
        total=len(collected),
        counts_by_type=counts,
        recommendations=collected[:limit],
    )
