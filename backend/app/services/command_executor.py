"""Command executor — maps classified commands to existing services.

All scoring, aggregation, and drafting logic lives in existing services
(pipeline, investor_agent, communications). This module only routes and
shapes output into the command_console response schema.

No LLM call path here. Unknown/unsupported intents return a structured
UnsupportedOutput or ClarificationOutput.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.integrations.investor_engine import drafts as engine_drafts
from app.integrations.investor_engine import service as engine_service
from app.services import intel as intel_service
from app.services import market as market_service
from app.services import program as program_service
from app.services import supplier as supplier_service
from app.services import executive as executive_service
from app.services import graph as graph_service
from app.services import recommendations as recommendations_service
from app.models.market import Account as _Account
from app.models.supplier import Supplier as _Supplier
from app.models.approval import Approval
from app.schemas.command_console import (
    ClarificationOutput,
    CommandClassification,
    CommandOutput,
    CommandRequest,
    CommandResponse,
    DraftOutput,
    EngineInvestorRow,
    EngineListOutput,
    EntityRef,
    MarketAccountRow,
    MarketCampaignRow,
    MarketFollowUpRow,
    MarketListOutput,
    MarketOpportunityRow,
    ProgramListOutput,
    ProgramRow,
    ProgramStageBucket,
    ProgramSupplierRow,
    SupplierListOutput,
    SupplierRow,
    ExecutiveActionQueueOutput,
    ExecutiveAlertsOutput,
    ExecutiveBriefingOutput,
    IntelListOutput,
    GraphAccountProgramsOutput,
    GraphInvestorMatchesOutput,
    GraphInvestorProgramsOutput,
    GraphRecommendationsOutput,
    GraphSupplierMatchesOutput,
    RankedOutput,
    ReviewItem,
    ReviewOutput,
    SummaryOutput,
    UnsupportedOutput,
)
from app.schemas.investor_agent import AgentFollowUpDraftRequest
from app.services import command_classifier as classifier
from app.services import command_history
from app.services import investor_agent as agent_service
from app.services import pipeline as pipeline_service

SUPPORTED_EXAMPLES = [
    "Show investor pipeline",
    "Show overdue follow-ups",
    "Show stale opportunities",
    "Rank investors most likely to close",
    "Prepare a brief for <firm name>",
    "Draft a follow-up for <firm name>",
    "Show pending approvals",
    "What investor actions matter most this week",
    "Show investor engine summary",
    "Show investor engine follow-ups due",
    "Show investors needing follow-up",
    "Show stale investor engine records",
    "Show investor engine records for <owner>",
    "Open investor engine record for <name>",
    "Draft a follow-up for <engine investor name> engine record",
    "Show target accounts",
    "Show active campaigns",
    "Show market opportunities",
    "Show accounts needing follow-up",
    "Show opportunities by sector",
    "Show active programs",
    "Show high-value programs",
    "Show programs by stage",
    "Show overdue programs",
    "Show program pipeline",
    "Show suppliers",
    "Show qualified suppliers",
    "Show suppliers by capability",
    "Show suppliers for program <name>",
    "Show onboarding pipeline",
    "What matters most today",
    "Show my action queue",
    "Show top risks",
    "Show overdue items across the system",
    "Show blocked programs",
    "Show supplier issues",
    "Show investor priorities",
    "Which investors match program <name>",
    "Which suppliers can support program <name>",
    "What accounts should we target",
    "Show recommended actions",
    "What industry news matters today",
    "Show top signals",
    "Show aerospace VC activity this week",
    "Show latest defense funding news",
    "Show top movers in aerospace and defense",
    "Show Europe defense signals",
    "Show intel by category",
    "Show watchlist signals",
]

import re as _re

_ENGINE_FOR_PATTERN = _re.compile(
    r"\bfor\s+([A-Za-z0-9][A-Za-z0-9&'.\- ]{1,60})\b", _re.IGNORECASE
)
_ENGINE_STALE_DAYS = 21


# ---------------------------------------------------------------------------
# intent handlers — each returns CommandOutput and status
# ---------------------------------------------------------------------------

def _run_pipeline_summary(db: Session) -> tuple[CommandOutput, str]:
    summary = agent_service.build_agent_pipeline_summary(db)
    insights = [f"{sc.stage}: {sc.count}" for sc in summary.stage_counts]
    next_actions: list[str] = []
    if summary.overdue_follow_up_count:
        next_actions.append(
            f"Resolve {summary.overdue_follow_up_count} overdue follow-up(s)."
        )
    if summary.missing_next_step_count:
        next_actions.append(
            f"Define next step on {summary.missing_next_step_count} opportunities."
        )
    if summary.stale_count:
        next_actions.append(
            f"Re-engage {summary.stale_count} stale opportunities."
        )
    return (
        SummaryOutput(
            headline=f"{summary.total_active} active investor opportunities.",
            key_insights=insights,
            supporting_data={
                "stale_threshold_days": summary.stale_threshold_days,
            },
            next_actions=next_actions,
            pipeline_summary=summary,
        ),
        "completed",
    )


def _run_overdue(db: Session) -> tuple[CommandOutput, str]:
    items = pipeline_service.list_overdue_summaries(db)
    return (
        RankedOutput(
            headline=f"{len(items)} overdue follow-up(s).",
            scoring_logic="Ordered by next_step_due_at ascending (most overdue first).",
            opportunities=items,
        ),
        "completed",
    )


def _run_stale(db: Session) -> tuple[CommandOutput, str]:
    items = pipeline_service.list_stale_summaries(db)
    return (
        RankedOutput(
            headline=f"{len(items)} stale opportunities (>21d since last interaction).",
            scoring_logic=(
                "Active opportunities whose last activity_event, sent communication, "
                "or meeting is null or older than 21 days. Ordered by oldest first."
            ),
            opportunities=items,
        ),
        "completed",
    )


def _run_prioritize(db: Session, limit: int = 10) -> tuple[CommandOutput, str]:
    ranked = agent_service.prioritize_opportunities(db, limit=limit)
    return (
        RankedOutput(
            headline=f"Top {ranked.count} priority investor opportunities.",
            scoring_logic=(
                "stage_weight + 0.4*probability + 0.4*strategic_value + 0.2*fit "
                "+ overdue_bonus − stale_penalty."
            ),
            items=ranked.results,
        ),
        "completed",
    )


def _run_brief(
    db: Session, classification: CommandClassification
) -> tuple[CommandOutput, str]:
    ref = classification.referenced_entity
    if ref is None or ref.entity_type != "investor_opportunity":
        return (
            ClarificationOutput(
                headline="Which opportunity?",
                message=(
                    "A brief requires a specific investor opportunity. Please "
                    "include a firm name (e.g. 'brief for Acme Ventures') or "
                    "opportunity id (e.g. 'brief for opportunity 42')."
                ),
                suggested_inputs=[
                    "Prepare a brief for <firm name>",
                    "Brief for opportunity <id>",
                ],
            ),
            "clarification_needed",
        )
    brief = agent_service.build_investor_brief(db, ref.entity_id)
    return (
        SummaryOutput(
            headline=f"Brief — {brief.firm_name or 'opportunity #' + str(brief.opportunity_id)}",
            key_insights=[
                f"Stage: {brief.stage}",
                brief.fit_assessment,
                brief.strategic_value_assessment,
            ],
            supporting_data={
                "days_since_last_interaction": brief.days_since_last_interaction,
                "blockers": brief.blockers,
            },
            next_actions=[brief.recommended_executive_focus],
            investor_brief=brief,
        ),
        "completed",
    )


def _run_pending_approvals(db: Session) -> tuple[CommandOutput, str]:
    stmt = (
        select(Approval)
        .where(Approval.status == "pending")
        .order_by(desc(Approval.created_at))
        .limit(100)
    )
    approvals = db.scalars(stmt).all()
    items = [
        ReviewItem(
            entity_type=a.entity_type,
            entity_id=a.entity_id,
            summary=f"{a.action} — requested by {a.requested_by or 'unknown'}",
            status=a.status,
            link_hint=f"/approvals/{a.id}",
        )
        for a in approvals
    ]
    return (
        ReviewOutput(
            headline=f"{len(items)} pending approval(s).",
            pending_approvals=items,
        ),
        "completed",
    )


def _run_blocked(db: Session) -> tuple[CommandOutput, str]:
    ranked = agent_service.prioritize_opportunities(db, limit=50)
    blocked: list[ReviewItem] = []
    for item in ranked.results:
        opp = item.opportunity
        reason: Optional[str] = None
        if not (opp.next_step and opp.next_step.strip()):
            reason = "missing next step"
        elif opp.next_step_due_at is not None and "overdue_by" in " ".join(item.factors):
            reason = "overdue follow-up"
        if reason:
            blocked.append(
                ReviewItem(
                    entity_type="investor_opportunity",
                    entity_id=opp.id,
                    summary=f"{opp.firm_name or 'opportunity #' + str(opp.id)} — {reason}",
                    status=opp.status,
                    link_hint=f"/investors/opportunities/{opp.id}",
                )
            )
    return (
        ReviewOutput(
            headline=f"{len(blocked)} blocked/incomplete investor item(s).",
            blocked_items=blocked,
        ),
        "completed",
    )


def _run_follow_up_draft(
    db: Session,
    request: CommandRequest,
    classification: CommandClassification,
    records_created: list[EntityRef],
) -> tuple[CommandOutput, str]:
    ref = classification.referenced_entity
    if ref is None or ref.entity_type != "investor_opportunity":
        return (
            ClarificationOutput(
                headline="Which opportunity should this draft target?",
                message=(
                    "A follow-up draft needs a specific investor opportunity. "
                    "Include a firm name or opportunity id."
                ),
                suggested_inputs=[
                    "Draft a follow-up for <firm name>",
                    "Draft a follow-up for opportunity <id>",
                ],
            ),
            "clarification_needed",
        )

    result = agent_service.orchestrate_follow_up_draft(
        db,
        ref.entity_id,
        AgentFollowUpDraftRequest(actor=request.actor, intent=request.text),
    )
    records_created.append(
        EntityRef(
            entity_type="communication",
            entity_id=result.communication.id,
            label=f"draft #{result.communication.id}",
        )
    )
    records_created.append(
        EntityRef(
            entity_type="workflow_run",
            entity_id=result.workflow_run.id,
            label=result.workflow_run.workflow_key,
        )
    )
    return (
        DraftOutput(
            headline=f"Draft #{result.communication.id} created for '{ref.label}'.",
            communication=result.communication,
            rationale=result.rationale,
            missing_context=result.missing_context,
            workflow_run=result.workflow_run,
        ),
        "completed",
    )


# ---------------------------------------------------------------------------
# investor engine handlers (read-only surface over the integration cache)
# ---------------------------------------------------------------------------


def _row_from_normalized(n) -> EngineInvestorRow:  # type: ignore[no-untyped-def]
    return EngineInvestorRow(
        external_id=n.external_id,
        firm_name=n.firm_name,
        stage=n.stage,
        owner=n.owner,
        follow_up_status=n.follow_up_status,
        last_touch_at=n.last_touch_at,
        next_follow_up_at=n.next_follow_up_at,
        next_step=n.next_step,
    )


def _run_engine_summary(db: Session) -> tuple[CommandOutput, str]:
    counts = engine_service.dashboard_summary(db)
    due = engine_service.follow_ups_due(db, limit=5)
    headline = (
        f"Investor engine · {counts.get('total', 0)} records, "
        f"{len(due)} follow-up(s) due."
    )
    return (
        EngineListOutput(
            headline=headline,
            rationale="Aggregated from the investor engine snapshot cache.",
            investors=[_row_from_normalized(n) for n in due],
            counts=counts,
        ),
        "completed",
    )


def _run_engine_follow_ups_due(db: Session) -> tuple[CommandOutput, str]:
    items = engine_service.follow_ups_due(db, limit=50)
    return (
        EngineListOutput(
            headline=f"{len(items)} investor engine follow-up(s) due.",
            rationale="Ordered by next_follow_up_at ascending (most overdue first).",
            investors=[_row_from_normalized(n) for n in items],
        ),
        "completed",
    )


def _run_engine_stale(db: Session) -> tuple[CommandOutput, str]:
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=_ENGINE_STALE_DAYS)
    items = engine_service.list_investors(db, limit=500)
    stale = [
        n
        for n in items
        if (n.last_touch_at is None) or (n.last_touch_at < cutoff)
    ]
    stale.sort(key=lambda n: n.last_touch_at or datetime.min.replace(tzinfo=timezone.utc))
    return (
        EngineListOutput(
            headline=(
                f"{len(stale)} stale investor engine record(s) "
                f"(>{_ENGINE_STALE_DAYS}d since last touch)."
            ),
            rationale=(
                f"Engine records whose last_touch_at is null or older than "
                f"{_ENGINE_STALE_DAYS} days."
            ),
            investors=[_row_from_normalized(n) for n in stale[:50]],
        ),
        "completed",
    )


def _run_engine_by_owner(
    db: Session, classification: CommandClassification, raw_text: str
) -> tuple[CommandOutput, str]:
    match = _ENGINE_FOR_PATTERN.search(raw_text)
    owner: Optional[str] = None
    if match:
        owner = match.group(1).strip().rstrip("?.! ").strip()
    if not owner:
        return (
            ClarificationOutput(
                headline="Which owner?",
                message=(
                    "Specify an owner — e.g. 'show investor engine records "
                    "for Brian Cook'."
                ),
                suggested_inputs=[
                    "Show investor engine records for <owner>",
                ],
            ),
            "clarification_needed",
        )
    items = engine_service.list_investors(db, owner=owner, limit=200)
    return (
        EngineListOutput(
            headline=f"{len(items)} investor engine record(s) owned by {owner}.",
            rationale=f"Filter: owner == {owner!r}",
            investors=[_row_from_normalized(n) for n in items],
        ),
        "completed",
    )


def _run_engine_follow_up_draft(
    db: Session,
    request: CommandRequest,
    raw_text: str,
    records_created: list[EntityRef],
) -> tuple[CommandOutput, str]:
    match = _ENGINE_FOR_PATTERN.search(raw_text)
    target: Optional[str] = None
    if match:
        target = match.group(1).strip().rstrip("?.! ").strip()
    if not target:
        return (
            ClarificationOutput(
                headline="Which engine record should this draft target?",
                message=(
                    "Include a firm name — e.g. 'draft a follow-up for "
                    "Acme Ventures engine record'."
                ),
                suggested_inputs=[
                    "Draft a follow-up for <engine investor name>",
                ],
            ),
            "clarification_needed",
        )

    all_items = engine_service.list_investors(db, limit=500)
    lower = target.lower()
    exact = [n for n in all_items if n.firm_name.lower() == lower]
    prefix = [n for n in all_items if n.firm_name.lower().startswith(lower)]
    pick = exact[0] if exact else (prefix[0] if len(prefix) == 1 else None)
    if pick is None:
        return (
            ClarificationOutput(
                headline=f"No engine record matched {target!r}.",
                message="Try a more specific firm name.",
                suggested_inputs=["Draft a follow-up for <engine investor name>"],
            ),
            "clarification_needed",
        )

    comm, run = engine_drafts.create_engine_follow_up_draft(
        db,
        pick.external_id,
        engine_drafts.EngineFollowUpDraftRequest(actor=request.actor),
    )
    records_created.append(
        EntityRef(
            entity_type="communication",
            entity_id=comm.id,
            label=f"draft #{comm.id}",
        )
    )
    records_created.append(
        EntityRef(
            entity_type="workflow_run",
            entity_id=run.id,
            label=run.workflow_key,
        )
    )
    return (
        DraftOutput(
            headline=(
                f"Draft #{comm.id} created from investor engine record "
                f"'{pick.firm_name}'."
            ),
            communication=comm,
            rationale=(
                f"Source: investor_engine · external_id={pick.external_id}. "
                "Draft is stored in Bifrost — nothing was written to the "
                "investor engine."
            ),
            missing_context=[],
            workflow_run=run,
        ),
        "completed",
    )


def _run_engine_open(
    db: Session, raw_text: str
) -> tuple[CommandOutput, str]:
    match = _ENGINE_FOR_PATTERN.search(raw_text)
    target: Optional[str] = None
    if match:
        target = match.group(1).strip().rstrip("?.! ").strip()
    if not target:
        return (
            ClarificationOutput(
                headline="Which investor engine record?",
                message=(
                    "Include a firm name — e.g. 'open investor engine record "
                    "for Acme Ventures'."
                ),
                suggested_inputs=["Open investor engine record for <name>"],
            ),
            "clarification_needed",
        )

    # Case-insensitive name match over the snapshot cache.
    all_items = engine_service.list_investors(db, limit=500)
    lower = target.lower()
    exact = [n for n in all_items if n.firm_name.lower() == lower]
    prefix = [n for n in all_items if n.firm_name.lower().startswith(lower)]
    pick = exact[0] if exact else (prefix[0] if len(prefix) == 1 else None)

    if pick is None:
        return (
            ClarificationOutput(
                headline=f"No engine record matched {target!r}.",
                message="Try a more specific firm name.",
                suggested_inputs=["Open investor engine record for <name>"],
            ),
            "clarification_needed",
        )
    return (
        EngineListOutput(
            headline=f"Investor engine — {pick.firm_name}",
            rationale=(
                f"Matched on firm_name. Open UI at /engine/{pick.external_id}."
            ),
            investors=[_row_from_normalized(pick)],
        ),
        "completed",
    )


# ---------------------------------------------------------------------------
# market os handlers
# ---------------------------------------------------------------------------

def _account_row(a) -> MarketAccountRow:
    return MarketAccountRow(
        id=a.id,
        name=a.name,
        sector=a.sector,
        region=a.region,
        type=a.type,
    )


def _campaign_row(c) -> MarketCampaignRow:
    return MarketCampaignRow(
        id=c.id,
        name=c.name,
        sector=c.sector,
        region=c.region,
        status=c.status,
    )


def _opportunity_row(opp) -> MarketOpportunityRow:
    return MarketOpportunityRow(
        id=opp.id,
        account_id=opp.account_id,
        account_name=opp.account.name if opp.account else None,
        name=opp.name,
        stage=opp.stage,
        sector=opp.account.sector if opp.account else None,
        next_step=opp.next_step,
        next_step_due_at=opp.next_step_due_at,
        estimated_value=float(opp.estimated_value) if opp.estimated_value is not None else None,
    )


def _follow_up_row(link) -> MarketFollowUpRow:
    return MarketFollowUpRow(
        link_id=link.id,
        account_id=link.account_id,
        account_name=link.account.name if link.account else None,
        campaign_id=link.campaign_id,
        campaign_name=link.campaign.name if link.campaign else None,
        status=link.status,
        next_follow_up_at=link.next_follow_up_at,
        last_contacted_at=link.last_contacted_at,
    )


def _run_market_accounts(db: Session) -> tuple[CommandOutput, str]:
    rows = market_service.list_accounts(db, limit=50)
    return (
        MarketListOutput(
            headline=f"{len(rows)} target account(s).",
            kind="accounts",
            rationale="Ordered by name. Filter via /accounts API.",
            accounts=[_account_row(a) for a in rows],
            counts={"total": len(rows)},
        ),
        "completed",
    )


def _run_market_campaigns(db: Session) -> tuple[CommandOutput, str]:
    rows = market_service.list_campaigns(db, status_="active", limit=50)
    return (
        MarketListOutput(
            headline=f"{len(rows)} active campaign(s).",
            kind="campaigns",
            rationale="Status = active.",
            campaigns=[_campaign_row(c) for c in rows],
            counts={"active": len(rows)},
        ),
        "completed",
    )


def _run_market_opportunities(db: Session) -> tuple[CommandOutput, str]:
    rows = market_service.list_active_opportunities(db, limit=50)
    return (
        MarketListOutput(
            headline=f"{len(rows)} active market opportunit(ies).",
            kind="opportunities",
            rationale="Stages: exploring, active.",
            opportunities=[_opportunity_row(o) for o in rows],
            counts={"active": len(rows)},
        ),
        "completed",
    )


def _run_market_follow_ups(db: Session) -> tuple[CommandOutput, str]:
    rows = market_service.accounts_needing_follow_up(db, limit=50)
    return (
        MarketListOutput(
            headline=f"{len(rows)} account/campaign pair(s) need follow-up.",
            kind="follow_ups",
            rationale="next_follow_up_at is at or before now.",
            follow_ups=[_follow_up_row(l) for l in rows],
            counts={"overdue_or_due": len(rows)},
        ),
        "completed",
    )


def _run_market_by_sector(db: Session) -> tuple[CommandOutput, str]:
    grouped = market_service.opportunities_by_sector(db)
    by_sector = {
        sector: [_opportunity_row(o) for o in opps]
        for sector, opps in grouped.items()
    }
    total = sum(len(v) for v in by_sector.values())
    return (
        MarketListOutput(
            headline=f"{total} opportunit(ies) across {len(by_sector)} sector(s).",
            kind="by_sector",
            rationale="Active opportunities grouped by account sector.",
            by_sector=by_sector,
            counts={
                "total": total,
                **{f"sector.{k}": len(v) for k, v in by_sector.items()},
            },
        ),
        "completed",
    )


# ---------------------------------------------------------------------------
# program os handlers
# ---------------------------------------------------------------------------

def _account_name_map(db: Session, programs) -> dict[int, str]:
    ids = {p.account_id for p in programs if p.account_id}
    if not ids:
        return {}
    rows = db.execute(
        select(_Account).where(_Account.id.in_(ids))
    ).scalars().all()
    return {a.id: a.name for a in rows}


def _program_row(p, account_names: dict[int, str]) -> ProgramRow:
    return ProgramRow(
        id=p.id,
        name=p.name,
        account_id=p.account_id,
        account_name=account_names.get(p.account_id),
        stage=p.stage,
        owner=p.owner,
        estimated_value=float(p.estimated_value)
        if p.estimated_value is not None
        else None,
        probability_score=p.probability_score,
        strategic_value_score=p.strategic_value_score,
        next_step=p.next_step,
        next_step_due_at=p.next_step_due_at,
    )


def _run_program_active(db: Session) -> tuple[CommandOutput, str]:
    rows = program_service.list_active_programs(db, limit=50)
    names = _account_name_map(db, rows)
    return (
        ProgramListOutput(
            headline=f"{len(rows)} active program(s).",
            kind="active",
            rationale="Stages: pursuing, active.",
            programs=[_program_row(p, names) for p in rows],
            counts={"active": len(rows)},
        ),
        "completed",
    )


def _run_program_high_value(db: Session) -> tuple[CommandOutput, str]:
    rows = program_service.list_high_value_programs(db, limit=25)
    names = _account_name_map(db, rows)
    return (
        ProgramListOutput(
            headline=f"{len(rows)} high-value program(s).",
            kind="high_value",
            rationale=(
                f"Estimated value ≥ {program_service.HIGH_VALUE_THRESHOLD:,.0f}"
            ),
            programs=[_program_row(p, names) for p in rows],
            counts={"high_value": len(rows)},
            totals={"threshold": program_service.HIGH_VALUE_THRESHOLD},
        ),
        "completed",
    )


def _run_program_overdue(db: Session) -> tuple[CommandOutput, str]:
    rows = program_service.list_overdue_programs(db, limit=50)
    names = _account_name_map(db, rows)
    return (
        ProgramListOutput(
            headline=f"{len(rows)} program(s) with overdue next steps.",
            kind="overdue",
            rationale="next_step_due_at ≤ now, stage ∈ (pursuing, active).",
            programs=[_program_row(p, names) for p in rows],
            counts={"overdue": len(rows)},
        ),
        "completed",
    )


def _run_program_pipeline(db: Session) -> tuple[CommandOutput, str]:
    data = program_service.pipeline_summary(db)
    highs = data["high_value"]
    overdues = data["overdue"]
    names = _account_name_map(db, list(highs) + list(overdues))
    counts = {
        "total": data["total_programs"],
        "active": data["active_count"],
        "won": data["won_count"],
        "lost": data["lost_count"],
        "high_value": data["high_value_count"],
        "overdue": data["overdue_count"],
    }
    return (
        ProgramListOutput(
            headline=(
                f"{data['total_programs']} program(s); {data['active_count']} active, "
                f"{data['high_value_count']} high-value, {data['overdue_count']} overdue."
            ),
            kind="pipeline",
            rationale="Aggregated program pipeline view.",
            programs=[_program_row(p, names) for p in highs]
            + [_program_row(p, names) for p in overdues if p.id not in {h.id for h in highs}],
            stage_counts=[
                ProgramStageBucket(stage=s["stage"], count=s["count"])
                for s in data["stage_counts"]
            ],
            counts=counts,
            totals={
                "estimated_value_active": data["total_estimated_value_active"],
                "high_value_threshold": data["high_value_threshold"],
            },
        ),
        "completed",
    )


def _run_program_by_stage(db: Session) -> tuple[CommandOutput, str]:
    rows = program_service.list_programs(db, limit=500)
    names = _account_name_map(db, rows)
    by_stage: dict[str, int] = {}
    for p in rows:
        by_stage[p.stage] = by_stage.get(p.stage, 0) + 1
    return (
        ProgramListOutput(
            headline=f"{len(rows)} program(s) across {len(by_stage)} stage(s).",
            kind="by_stage",
            rationale="All non-deleted programs grouped by stage.",
            programs=[_program_row(p, names) for p in rows],
            stage_counts=[
                ProgramStageBucket(stage=s, count=c)
                for s, c in sorted(by_stage.items())
            ],
            counts={"total": len(rows)},
        ),
        "completed",
    )


# ---------------------------------------------------------------------------
# supplier os handlers
# ---------------------------------------------------------------------------

_SUPPLIER_FOR_PATTERN = _re.compile(
    r"\bfor\s+(?:program\s+)?([A-Za-z0-9][A-Za-z0-9&'.\- ]{1,80})$",
    _re.IGNORECASE,
)


def _supplier_row(s, *, include_related: bool = False) -> SupplierRow:
    capabilities: list[str] = []
    certifications: list[str] = []
    if include_related:
        capabilities = [c.capability_type for c in getattr(s, "capabilities", [])]
        certifications = [
            c.certification for c in getattr(s, "certifications", [])
        ]
    return SupplierRow(
        id=s.id,
        name=s.name,
        type=s.type,
        region=s.region,
        country=s.country,
        onboarding_status=s.onboarding_status,
        preferred_partner_score=s.preferred_partner_score,
        capabilities=capabilities,
        certifications=certifications,
    )


def _run_supplier_all(db: Session) -> tuple[CommandOutput, str]:
    rows = supplier_service.list_suppliers(db, limit=100)
    return (
        SupplierListOutput(
            headline=f"{len(rows)} supplier(s).",
            kind="all",
            rationale="All non-deleted suppliers, ordered by name.",
            suppliers=[_supplier_row(s) for s in rows],
            counts={"total": len(rows)},
        ),
        "completed",
    )


def _run_supplier_qualified(db: Session) -> tuple[CommandOutput, str]:
    rows = supplier_service.list_qualified_suppliers(db, limit=100)
    return (
        SupplierListOutput(
            headline=f"{len(rows)} qualified/onboarded supplier(s).",
            kind="qualified",
            rationale="onboarding_status ∈ (qualified, onboarded).",
            suppliers=[_supplier_row(s) for s in rows],
            counts={"qualified_or_onboarded": len(rows)},
        ),
        "completed",
    )


def _run_supplier_by_capability(db: Session) -> tuple[CommandOutput, str]:
    grouped = supplier_service.suppliers_by_capability(db)
    by_capability = {
        cap: [_supplier_row(s) for s in sups] for cap, sups in grouped.items()
    }
    total = sum(len(v) for v in by_capability.values())
    return (
        SupplierListOutput(
            headline=(
                f"{total} supplier/capability pairing(s) across "
                f"{len(by_capability)} capabilit(ies)."
            ),
            kind="by_capability",
            rationale="Suppliers grouped by declared capability_type.",
            by_capability=by_capability,
            counts={"total": total, **{f"cap.{k}": len(v) for k, v in by_capability.items()}},
        ),
        "completed",
    )


def _run_supplier_for_program(
    db: Session, raw_text: str
) -> tuple[CommandOutput, str]:
    match = _SUPPLIER_FOR_PATTERN.search(raw_text.strip())
    name = (match.group(1).strip().rstrip("?.! ") if match else "").strip()
    if not name:
        return (
            ClarificationOutput(
                headline="Which program?",
                message=(
                    "Specify which program's suppliers to show, e.g. "
                    "'Show suppliers for program Apollo'."
                ),
                candidates=[],
                suggested_inputs=[
                    "Show suppliers for program <name>",
                    "Show qualified suppliers",
                ],
            ),
            "clarification_needed",
        )
    prog = supplier_service.find_program_by_name(db, name)
    if prog is None:
        return (
            ClarificationOutput(
                headline=f"No program matched '{name}'.",
                message=(
                    "Try the exact program name, or use 'List programs' to see "
                    "what's available."
                ),
                candidates=[],
                suggested_inputs=["List programs"],
            ),
            "clarification_needed",
        )
    links = supplier_service.list_program_suppliers(db, program_id=prog.id)
    rows: list[ProgramSupplierRow] = []
    for l in links:
        sup = db.get(_Supplier, l.supplier_id)
        rows.append(
            ProgramSupplierRow(
                link_id=l.id,
                program_id=l.program_id,
                program_name=prog.name,
                supplier_id=l.supplier_id,
                supplier_name=sup.name if sup else None,
                role=l.role,
                status=l.status,
            )
        )
    return (
        SupplierListOutput(
            headline=(
                f"{len(rows)} supplier(s) linked to program '{prog.name}'."
            ),
            kind="for_program",
            rationale=(
                f"program_id={prog.id}; role/status from program_suppliers."
            ),
            program_links=rows,
            counts={"total": len(rows)},
        ),
        "completed",
    )


def _run_supplier_onboarding(db: Session) -> tuple[CommandOutput, str]:
    data = supplier_service.onboarding_summary(db)
    counts = {"total": data["total"], **{
        f"status.{k}": v for k, v in data["by_status"].items()
    }}
    counts["qualified"] = data["qualified"]
    counts["onboarded"] = data["onboarded"]
    counts["active_program_links"] = data["active_program_supplier_count"]
    return (
        SupplierListOutput(
            headline=(
                f"{data['total']} supplier(s); {data['qualified']} qualified, "
                f"{data['onboarded']} onboarded."
            ),
            kind="onboarding",
            rationale="Onboarding pipeline snapshot.",
            counts=counts,
        ),
        "completed",
    )


# ---------------------------------------------------------------------------
# executive os handlers
# ---------------------------------------------------------------------------

def _run_exec_briefing(db: Session) -> tuple[CommandOutput, str]:
    briefing = executive_service.build_briefing(db)
    return (
        ExecutiveBriefingOutput(
            headline=briefing.headline,
            briefing=briefing,
        ),
        "completed",
    )


def _run_exec_queue(
    db: Session, *, domain: Optional[str] = None, limit: int = 25
) -> tuple[CommandOutput, str]:
    full = executive_service.build_action_queue(db, limit=500)
    items = full.items
    if domain:
        items = [i for i in items if i.domain == domain]
    counts: dict[str, int] = {}
    for i in items:
        counts[i.domain] = counts.get(i.domain, 0) + 1
    clipped = items[:limit]
    from app.schemas.executive import ActionQueue as _AQ
    queue = _AQ(
        generated_at=full.generated_at,
        total=len(items),
        counts_by_domain=counts,
        items=clipped,
    )
    headline = (
        f"{len(items)} action(s) in queue"
        + (f" · {domain}" if domain else "")
        + "."
    )
    return (
        ExecutiveActionQueueOutput(headline=headline, queue=queue),
        "completed",
    )


def _run_exec_alerts(
    db: Session, *, severity: Optional[str] = None
) -> tuple[CommandOutput, str]:
    full = executive_service.build_alerts(db)
    alerts = full.alerts
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    counts: dict[str, int] = {}
    for a in alerts:
        counts[a.severity] = counts.get(a.severity, 0) + 1
    from app.schemas.executive import AlertBundle as _AB
    bundle = _AB(
        generated_at=full.generated_at,
        total=len(alerts),
        counts_by_severity=counts,
        alerts=alerts,
    )
    headline = (
        f"{len(alerts)} alert(s)"
        + (f" at {severity}" if severity else "")
        + "."
    )
    return ExecutiveAlertsOutput(headline=headline, alerts=bundle), "completed"


# ---------------------------------------------------------------------------
# graph intelligence handlers
# ---------------------------------------------------------------------------

_GRAPH_PROGRAM_PATTERN = _re.compile(
    r"\b(?:for\s+)?program\s+([A-Za-z0-9][A-Za-z0-9&'.\- ]{1,80})$",
    _re.IGNORECASE,
)


def _extract_program_name(raw_text: str) -> Optional[str]:
    match = _GRAPH_PROGRAM_PATTERN.search(raw_text.strip())
    if not match:
        return None
    return match.group(1).strip().rstrip("?.! ").strip() or None


def _run_graph_recommendations(db: Session) -> tuple[CommandOutput, str]:
    bundle = recommendations_service.build_recommendations(db, limit=100)
    headline = (
        f"{bundle.total} graph recommendation(s) across "
        f"{len(bundle.counts_by_type)} type(s)."
    )
    return (
        GraphRecommendationsOutput(headline=headline, recommendations=bundle),
        "completed",
    )


def _run_graph_investors_for_program(
    db: Session, raw_text: str
) -> tuple[CommandOutput, str]:
    name = _extract_program_name(raw_text)
    if not name:
        return (
            ClarificationOutput(
                headline="Which program?",
                message=(
                    "Specify a program, e.g. 'which investors match program "
                    "Apollo'."
                ),
                suggested_inputs=[
                    "Which investors match program <name>",
                    "Show recommended actions",
                ],
            ),
            "clarification_needed",
        )
    prog = supplier_service.find_program_by_name(db, name)
    if prog is None:
        return (
            ClarificationOutput(
                headline=f"No program matched '{name}'.",
                message="Try the exact program name, or run 'List programs'.",
                suggested_inputs=["List programs"],
            ),
            "clarification_needed",
        )
    result = graph_service.match_investors_for_program(db, prog.id, limit=25)
    return (
        GraphInvestorMatchesOutput(
            headline=(
                f"{len(result.matches)} investor match(es) for program "
                f"'{prog.name}'."
            ),
            matches=result,
        ),
        "completed",
    )


def _run_graph_suppliers_for_program(
    db: Session, raw_text: str
) -> tuple[CommandOutput, str]:
    name = _extract_program_name(raw_text)
    if not name:
        return (
            ClarificationOutput(
                headline="Which program?",
                message=(
                    "Specify a program, e.g. 'which suppliers can support "
                    "program Apollo'."
                ),
                suggested_inputs=[
                    "Which suppliers can support program <name>",
                ],
            ),
            "clarification_needed",
        )
    prog = supplier_service.find_program_by_name(db, name)
    if prog is None:
        return (
            ClarificationOutput(
                headline=f"No program matched '{name}'.",
                message="Try the exact program name, or run 'List programs'.",
                suggested_inputs=["List programs"],
            ),
            "clarification_needed",
        )
    result = graph_service.match_suppliers_for_program(db, prog.id, limit=25)
    return (
        GraphSupplierMatchesOutput(
            headline=(
                f"{len(result.matches)} supplier match(es) for program "
                f"'{prog.name}'."
            ),
            matches=result,
        ),
        "completed",
    )


def _run_graph_accounts_to_target(db: Session) -> tuple[CommandOutput, str]:
    bundle = recommendations_service.build_recommendations(
        db, types=["account_to_pursue"], limit=50
    )
    headline = f"{bundle.total} target account recommendation(s)."
    return (
        GraphRecommendationsOutput(headline=headline, recommendations=bundle),
        "completed",
    )


# ---------------------------------------------------------------------------
# intelligence os handlers
# ---------------------------------------------------------------------------


def _intel_items_read(items) -> list:
    from app.schemas.intel import IntelItemRead

    return [IntelItemRead.model_validate(i) for i in items]


def _run_intel_top_signals(db: Session) -> tuple[CommandOutput, str]:
    items = intel_service.top_signals(db, limit=10)
    return (
        IntelListOutput(
            headline=f"{len(items)} top strategic signal(s).",
            kind="top_signals",
            rationale=(
                f"strategic_relevance_score ≥ "
                f"{intel_service.TOP_SIGNAL_MIN_SCORE}, ordered by relevance "
                "then urgency then recency."
            ),
            items=_intel_items_read(items),
            counts={"total": len(items)},
        ),
        "completed",
    )


def _run_intel_news_today(db: Session) -> tuple[CommandOutput, str]:
    items = intel_service.top_signals(db, limit=15)
    return (
        IntelListOutput(
            headline=(
                f"{len(items)} industry item(s) matter today "
                "across venture, defense, and aerospace."
            ),
            kind="news_today",
            rationale="Top-relevance intel items sorted by urgency and recency.",
            items=_intel_items_read(items),
            counts={"total": len(items)},
        ),
        "completed",
    )


def _run_intel_vc_activity(db: Session) -> tuple[CommandOutput, str]:
    items = intel_service.list_intel_items(
        db, category="vc_funding", limit=25
    )
    return (
        IntelListOutput(
            headline=f"{len(items)} VC activity signal(s).",
            kind="vc_activity",
            rationale="Items classified as vc_funding.",
            items=_intel_items_read(items),
            counts={"total": len(items)},
        ),
        "completed",
    )


def _run_intel_defense_funding(db: Session) -> tuple[CommandOutput, str]:
    # Defense-funding is the intersection of defense_tech and vc_funding-
    # style items. We surface both, prefer high-relevance.
    defense = intel_service.list_intel_items(db, category="defense_tech", limit=25)
    funding = intel_service.list_intel_items(db, category="vc_funding", limit=25)
    merged: list = []
    seen: set[int] = set()
    for i in defense + funding:
        if i.id in seen:
            continue
        seen.add(i.id)
        merged.append(i)
    merged.sort(
        key=lambda r: (
            -r.strategic_relevance_score,
            -r.urgency_score,
        )
    )
    return (
        IntelListOutput(
            headline=f"{len(merged)} defense-funding signal(s).",
            kind="defense_funding",
            rationale="Union of defense_tech and vc_funding categories.",
            items=_intel_items_read(merged[:25]),
            counts={
                "defense_tech": len(defense),
                "vc_funding": len(funding),
                "total": len(merged),
            },
        ),
        "completed",
    )


def _run_intel_top_movers(db: Session) -> tuple[CommandOutput, str]:
    items = intel_service.list_intel_items(
        db, tag="market-relevant", limit=25
    )
    return (
        IntelListOutput(
            headline=f"{len(items)} top mover signal(s) in aerospace and defense.",
            kind="top_movers",
            rationale=(
                "Tagged market-relevant — acquisitions, partnerships, and "
                "major-player moves."
            ),
            items=_intel_items_read(items),
            counts={"total": len(items)},
        ),
        "completed",
    )


def _run_intel_by_region(
    db: Session, raw_text: str
) -> tuple[CommandOutput, str]:
    lower = raw_text.lower()
    region_filter: Optional[str] = None
    for token, region in [
        ("europe", "Europe"),
        ("us ", "US"),
        ("u.s.", "US"),
        ("united states", "US"),
        ("asia", "Asia-Pacific"),
        ("pacific", "Asia-Pacific"),
        ("middle east", "Middle East"),
        ("global", "Global"),
    ]:
        if token in lower:
            region_filter = region
            break

    if region_filter:
        items = intel_service.list_intel_items(db, region=region_filter, limit=25)
        return (
            IntelListOutput(
                headline=f"{len(items)} intel signal(s) from {region_filter}.",
                kind="by_region",
                rationale=f"Filter: region == {region_filter!r}.",
                items=_intel_items_read(items),
                counts={region_filter: len(items)},
            ),
            "completed",
        )

    grouped = intel_service.group_by_region(db, limit_per_region=5)
    by_region = {
        region: _intel_items_read(v) for region, v in grouped.items()
    }
    total = sum(len(v) for v in by_region.values())
    return (
        IntelListOutput(
            headline=f"{total} intel signal(s) across {len(by_region)} region(s).",
            kind="by_region",
            rationale="All intel items grouped by detected region.",
            by_region=by_region,
            counts={"total": total, **{f"region.{k}": len(v) for k, v in by_region.items()}},
        ),
        "completed",
    )


def _run_intel_by_category(db: Session) -> tuple[CommandOutput, str]:
    grouped = intel_service.group_by_category(db, limit_per_category=5)
    by_category = {
        cat: _intel_items_read(v) for cat, v in grouped.items()
    }
    total = sum(len(v) for v in by_category.values())
    return (
        IntelListOutput(
            headline=f"{total} intel signal(s) across {len(by_category)} categor(ies).",
            kind="by_category",
            rationale="All intel items grouped by category.",
            by_category=by_category,
            counts={"total": total, **{f"cat.{k}": len(v) for k, v in by_category.items()}},
        ),
        "completed",
    )


def _run_intel_watchlist(db: Session) -> tuple[CommandOutput, str]:
    items = intel_service.list_intel_items(db, tag="watchlist", limit=25)
    return (
        IntelListOutput(
            headline=f"{len(items)} watchlist signal(s).",
            kind="watchlist",
            rationale="Tagged watchlist — key players Asgard is tracking.",
            items=_intel_items_read(items),
            counts={"total": len(items)},
        ),
        "completed",
    )


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------

_UNSUPPORTED_REASONS = {
    classifier.INTENT_UNKNOWN: (
        "Command could not be matched to a supported Phase 1 investor action."
    ),
}


def _unsupported(reason: str) -> tuple[CommandOutput, str]:
    return (
        UnsupportedOutput(
            headline="Command not supported in Phase 1.",
            reason=reason,
            supported_examples=SUPPORTED_EXAMPLES,
        ),
        "unsupported",
    )


def execute(db: Session, request: CommandRequest) -> CommandResponse:
    started = datetime.now(timezone.utc)
    started_ms = started.timestamp() * 1000.0

    normalized, classification = classifier.classify(
        db, request.text, context_entity=request.context_entity
    )

    records_created: list[EntityRef] = []

    intent = classification.intent
    if intent == classifier.INTENT_PIPELINE_SUMMARY:
        output, status = _run_pipeline_summary(db)
    elif intent == classifier.INTENT_OVERDUE:
        output, status = _run_overdue(db)
    elif intent == classifier.INTENT_STALE:
        output, status = _run_stale(db)
    elif intent == classifier.INTENT_PRIORITIZE:
        output, status = _run_prioritize(db)
    elif intent == classifier.INTENT_PLAN_THIS_WEEK:
        output, status = _run_prioritize(db)
    elif intent == classifier.INTENT_BRIEF:
        output, status = _run_brief(db, classification)
    elif intent == classifier.INTENT_PENDING_APPROVALS:
        output, status = _run_pending_approvals(db)
    elif intent == classifier.INTENT_REVIEW_BLOCKED:
        output, status = _run_blocked(db)
    elif intent == classifier.INTENT_FOLLOW_UP_DRAFT:
        output, status = _run_follow_up_draft(
            db, request, classification, records_created
        )
    elif intent == classifier.INTENT_ENGINE_SUMMARY:
        output, status = _run_engine_summary(db)
    elif intent == classifier.INTENT_ENGINE_FOLLOW_UPS_DUE:
        output, status = _run_engine_follow_ups_due(db)
    elif intent == classifier.INTENT_ENGINE_STALE:
        output, status = _run_engine_stale(db)
    elif intent == classifier.INTENT_ENGINE_BY_OWNER:
        output, status = _run_engine_by_owner(db, classification, request.text)
    elif intent == classifier.INTENT_ENGINE_OPEN_RECORD:
        output, status = _run_engine_open(db, request.text)
    elif intent == classifier.INTENT_ENGINE_FOLLOW_UP_DRAFT:
        output, status = _run_engine_follow_up_draft(
            db, request, request.text, records_created
        )
    elif intent == classifier.INTENT_MARKET_ACCOUNTS:
        output, status = _run_market_accounts(db)
    elif intent == classifier.INTENT_MARKET_CAMPAIGNS:
        output, status = _run_market_campaigns(db)
    elif intent == classifier.INTENT_MARKET_OPPORTUNITIES:
        output, status = _run_market_opportunities(db)
    elif intent == classifier.INTENT_MARKET_FOLLOW_UPS:
        output, status = _run_market_follow_ups(db)
    elif intent == classifier.INTENT_MARKET_BY_SECTOR:
        output, status = _run_market_by_sector(db)
    elif intent == classifier.INTENT_PROGRAM_ACTIVE:
        output, status = _run_program_active(db)
    elif intent == classifier.INTENT_PROGRAM_HIGH_VALUE:
        output, status = _run_program_high_value(db)
    elif intent == classifier.INTENT_PROGRAM_OVERDUE:
        output, status = _run_program_overdue(db)
    elif intent == classifier.INTENT_PROGRAM_BY_STAGE:
        output, status = _run_program_by_stage(db)
    elif intent == classifier.INTENT_PROGRAM_PIPELINE:
        output, status = _run_program_pipeline(db)
    elif intent == classifier.INTENT_SUPPLIER_ALL:
        output, status = _run_supplier_all(db)
    elif intent == classifier.INTENT_SUPPLIER_QUALIFIED:
        output, status = _run_supplier_qualified(db)
    elif intent == classifier.INTENT_SUPPLIER_BY_CAPABILITY:
        output, status = _run_supplier_by_capability(db)
    elif intent == classifier.INTENT_SUPPLIER_FOR_PROGRAM:
        output, status = _run_supplier_for_program(db, request.text)
    elif intent == classifier.INTENT_SUPPLIER_ONBOARDING:
        output, status = _run_supplier_onboarding(db)
    elif intent == classifier.INTENT_EXEC_BRIEFING:
        output, status = _run_exec_briefing(db)
    elif intent == classifier.INTENT_EXEC_QUEUE:
        output, status = _run_exec_queue(db)
    elif intent == classifier.INTENT_EXEC_ALERTS:
        output, status = _run_exec_alerts(db)
    elif intent == classifier.INTENT_EXEC_OVERDUE_ALL:
        # Filter the unified queue to overdue-style kinds.
        full = executive_service.build_action_queue(db, limit=500)
        overdue_kinds = {
            "investor_overdue_follow_up",
            "market_follow_up_due",
            "program_overdue_next_step",
            "engine_write_failed",
        }
        filtered = [i for i in full.items if i.kind in overdue_kinds]
        counts: dict[str, int] = {}
        for i in filtered:
            counts[i.domain] = counts.get(i.domain, 0) + 1
        from app.schemas.executive import ActionQueue as _AQ
        q = _AQ(
            generated_at=full.generated_at,
            total=len(filtered),
            counts_by_domain=counts,
            items=filtered[:50],
        )
        output, status = (
            ExecutiveActionQueueOutput(
                headline=f"{len(filtered)} overdue item(s) across the system.",
                queue=q,
            ),
            "completed",
        )
    elif intent == classifier.INTENT_EXEC_BLOCKED_PROGRAMS:
        # Programs missing suppliers OR with overdue next steps.
        full = executive_service.build_action_queue(db, limit=500)
        kinds = {"program_overdue_next_step", "program_missing_supplier"}
        filtered = [i for i in full.items if i.kind in kinds]
        counts = {}
        for i in filtered:
            counts[i.domain] = counts.get(i.domain, 0) + 1
        from app.schemas.executive import ActionQueue as _AQ
        q = _AQ(
            generated_at=full.generated_at,
            total=len(filtered),
            counts_by_domain=counts,
            items=filtered[:50],
        )
        output, status = (
            ExecutiveActionQueueOutput(
                headline=f"{len(filtered)} blocked program(s).",
                queue=q,
            ),
            "completed",
        )
    elif intent == classifier.INTENT_EXEC_SUPPLIER_ISSUES:
        bundle = executive_service.build_alerts(db)
        filtered = [a for a in bundle.alerts if a.domain == "supplier"]
        from app.schemas.executive import AlertBundle as _AB
        counts = {}
        for a in filtered:
            counts[a.severity] = counts.get(a.severity, 0) + 1
        b = _AB(
            generated_at=bundle.generated_at,
            total=len(filtered),
            counts_by_severity=counts,
            alerts=filtered,
        )
        output, status = (
            ExecutiveAlertsOutput(
                headline=f"{len(filtered)} supplier issue(s).",
                alerts=b,
            ),
            "completed",
        )
    elif intent == classifier.INTENT_GRAPH_RECOMMENDATIONS:
        output, status = _run_graph_recommendations(db)
    elif intent == classifier.INTENT_GRAPH_INVESTORS_FOR_PROGRAM:
        output, status = _run_graph_investors_for_program(db, request.text)
    elif intent == classifier.INTENT_GRAPH_SUPPLIERS_FOR_PROGRAM:
        output, status = _run_graph_suppliers_for_program(db, request.text)
    elif intent == classifier.INTENT_GRAPH_ACCOUNTS_TO_TARGET:
        output, status = _run_graph_accounts_to_target(db)
    elif intent == classifier.INTENT_EXEC_INVESTOR_PRIORITIES:
        # Reuse the existing INTENT_PRIORITIZE path directly.
        output, status = _run_prioritize(db)
    elif intent == classifier.INTENT_INTEL_TOP_SIGNALS:
        output, status = _run_intel_top_signals(db)
    elif intent == classifier.INTENT_INTEL_NEWS_TODAY:
        output, status = _run_intel_news_today(db)
    elif intent == classifier.INTENT_INTEL_VC_ACTIVITY:
        output, status = _run_intel_vc_activity(db)
    elif intent == classifier.INTENT_INTEL_DEFENSE_FUNDING:
        output, status = _run_intel_defense_funding(db)
    elif intent == classifier.INTENT_INTEL_TOP_MOVERS:
        output, status = _run_intel_top_movers(db)
    elif intent == classifier.INTENT_INTEL_BY_REGION:
        output, status = _run_intel_by_region(db, request.text)
    elif intent == classifier.INTENT_INTEL_BY_CATEGORY:
        output, status = _run_intel_by_category(db)
    elif intent == classifier.INTENT_INTEL_WATCHLIST:
        output, status = _run_intel_watchlist(db)
    else:
        output, status = _unsupported(
            _UNSUPPORTED_REASONS.get(intent, "Unsupported intent.")
        )

    finished = datetime.now(timezone.utc)
    duration_ms = max(0, int(finished.timestamp() * 1000.0 - started_ms))

    history_event = command_history.record_command(
        db,
        actor=request.actor,
        command_text=request.text,
        normalized_text=normalized,
        classification=classification,
        output_type=output.output_type,
        status=status,
        duration_ms=duration_ms,
        records_created=records_created,
    )

    return CommandResponse(
        command_text=request.text,
        normalized_text=normalized,
        classification=classification,
        status=status,  # type: ignore[arg-type]
        output=output,
        records_created=records_created,
        duration_ms=duration_ms,
        executed_at=finished,
        history_id=history_event.id,
    )
