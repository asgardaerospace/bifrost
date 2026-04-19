"""Executive OS service — cross-domain aggregation, action queue, alerts.

This module is a thin aggregator over the existing domain services. It
deliberately does not duplicate business logic — every query below is
a read against:

    - services.pipeline              (investor pipeline state)
    - services.investor_agent        (investor pipeline summary)
    - integrations.investor_engine.* (engine snapshots, pending writes)
    - services.market                (accounts, campaigns, opportunities)
    - services.program               (programs pipeline)
    - services.supplier              (suppliers, onboarding, program links)
    - models.approval.Approval       (pending approvals)

Priority scoring is deterministic and expressed directly in code so the
operator can inspect and adjust weights without tracing model calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.investor_engine import service as engine_service
from app.integrations.investor_engine.writes_models import (
    PendingEngineWrite,
    STATUS_FAILED,
    STATUS_PENDING,
)
from app.models.approval import Approval
from app.models.market import Account, AccountCampaign, MarketOpportunity
from app.models.program import Program
from app.models.supplier import (
    ProgramSupplier,
    Supplier,
    SupplierCertification,
)
from app.schemas.executive import (
    ActionItem,
    ActionQueue,
    Alert,
    AlertBundle,
    BriefingItem,
    BriefingSection,
    DailyBriefing,
    ExecutiveMetrics,
)
from app.services import investor_agent as agent_service
from app.services import market as market_service
from app.services import pipeline as pipeline_service
from app.services import program as program_service
from app.services import recommendations as recommendations_service
from app.services import supplier as supplier_service


PENDING_APPROVAL_STALE_HOURS = 48
DILIGENCE_STAGE_NAMES = ("diligence", "due_diligence")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_between(a: Optional[datetime], b: datetime) -> Optional[int]:
    if a is None:
        return None
    a_aware = a if a.tzinfo is not None else a.replace(tzinfo=timezone.utc)
    return (b - a_aware).days


# ---------------------------------------------------------------------------
# priority scoring
# ---------------------------------------------------------------------------
#
# All scoring lives here. The rule of thumb: higher score = more urgent.
# Scoring is clipped into [0, 100]. Weights are intentionally coarse — this
# is a daily triage signal, not a forecast. Documented in the explanation
# at the end of this change.
#
# Base weights by source:
#
#   overdue investor follow-up        : 70 + days_overdue*2   (capped)
#   missing investor next step        : 55
#   stale investor opportunity        : 50 + days_stale       (capped)
#   pending approval                  : 60 + hours_waiting*0.5
#   overdue program next step         : 75 + days_overdue*2
#   high-value program, no supplier   : 72
#   active account with no next step  : 45
#   market follow-up due              : 60 + days_overdue*2
#   supplier onboarding stuck         : 45
#   engine write failed/stale         : 85
#

def _clip(score: float) -> int:
    return max(0, min(100, int(round(score))))


# ---------------------------------------------------------------------------
# action queue
# ---------------------------------------------------------------------------


def _actions_investor_overdue(db: Session) -> list[ActionItem]:
    now = _now()
    rows = pipeline_service.list_overdue_summaries(db)
    out: list[ActionItem] = []
    for opp in rows:
        due = opp.next_step_due_at
        days_overdue = max(0, _days_between(due, now) or 0)
        out.append(
            ActionItem(
                id=f"capital.overdue.{opp.id}",
                domain="capital",
                kind="investor_overdue_follow_up",
                title=(
                    f"Follow up: {opp.firm_name or f'opportunity #{opp.id}'}"
                ),
                description=opp.next_step or "No next step set.",
                priority_score=_clip(70 + days_overdue * 2),
                due_at=due,
                status=opp.status,
                related_entity_type="investor_opportunity",
                related_entity_id=opp.id,
                source_label="Capital · overdue",
                link_hint=f"/investors/{opp.firm_id}" if opp.firm_id else None,
            )
        )
    return out


def _actions_investor_missing(db: Session) -> list[ActionItem]:
    rows = pipeline_service.list_missing_next_step(db)
    out: list[ActionItem] = []
    for opp in rows:
        name = getattr(opp.firm, "name", None) if getattr(opp, "firm", None) else None
        out.append(
            ActionItem(
                id=f"capital.missing.{opp.id}",
                domain="capital",
                kind="investor_missing_next_step",
                title=f"Set next step: {name or f'opportunity #{opp.id}'}",
                description="No next step recorded; opportunity will drift.",
                priority_score=55,
                status=opp.status,
                related_entity_type="investor_opportunity",
                related_entity_id=opp.id,
                source_label="Capital · missing next step",
            )
        )
    return out


def _actions_investor_stale(db: Session) -> list[ActionItem]:
    now = _now()
    summaries = pipeline_service.list_stale_summaries(db)
    out: list[ActionItem] = []
    for opp in summaries:
        days_stale = opp.days_since_last_interaction or 0
        out.append(
            ActionItem(
                id=f"capital.stale.{opp.id}",
                domain="capital",
                kind="investor_stale",
                title=f"Re-engage: {opp.firm_name or f'opportunity #{opp.id}'}",
                description=(
                    f"No interaction for {days_stale} day(s)."
                    if days_stale
                    else "No interaction recorded."
                ),
                priority_score=_clip(50 + days_stale),
                status=opp.status,
                related_entity_type="investor_opportunity",
                related_entity_id=opp.id,
                source_label="Capital · stale",
                link_hint=(
                    f"/investors/{opp.firm_id}" if opp.firm_id else None
                ),
            )
        )
    return out


def _actions_pending_approvals(db: Session) -> list[ActionItem]:
    now = _now()
    rows = db.execute(
        select(Approval).where(Approval.status == "pending")
    ).scalars().all()
    out: list[ActionItem] = []
    for a in rows:
        created = a.created_at if a.created_at is not None else now
        created_aware = (
            created if created.tzinfo is not None
            else created.replace(tzinfo=timezone.utc)
        )
        hours_waiting = max(0, int((now - created_aware).total_seconds() // 3600))
        out.append(
            ActionItem(
                id=f"approval.{a.id}",
                domain="approval",
                kind=f"approval.{a.action}",
                title=f"Review approval #{a.id}: {a.action}",
                description=(
                    f"{a.entity_type} #{a.entity_id} "
                    f"requested by {a.requested_by or 'unknown'}."
                ),
                priority_score=_clip(60 + hours_waiting * 0.5),
                status=a.status,
                related_entity_type=a.entity_type,
                related_entity_id=a.entity_id,
                source_label="Approval queue",
                link_hint="/approvals",
            )
        )
    return out


def _actions_market_follow_ups(db: Session) -> list[ActionItem]:
    now = _now()
    rows = market_service.accounts_needing_follow_up(db, limit=200)
    out: list[ActionItem] = []
    for link in rows:
        days_overdue = max(0, _days_between(link.next_follow_up_at, now) or 0)
        account_name = link.account.name if link.account else f"account #{link.account_id}"
        campaign_name = (
            link.campaign.name if link.campaign else f"campaign #{link.campaign_id}"
        )
        out.append(
            ActionItem(
                id=f"market.follow_up.{link.id}",
                domain="market",
                kind="market_follow_up_due",
                title=f"Follow up: {account_name} ({campaign_name})",
                description=f"Outreach status: {link.status}.",
                priority_score=_clip(60 + days_overdue * 2),
                due_at=link.next_follow_up_at,
                status=link.status,
                related_entity_type="account_campaign",
                related_entity_id=link.id,
                source_label="Market · follow-ups",
                link_hint="/market",
            )
        )
    return out


def _actions_market_accounts_no_next_step(db: Session) -> list[ActionItem]:
    """Accounts with active opportunities but no associated next step.

    Derived from the MarketOpportunity table: an account has an active
    opportunity (stage in {exploring, active}) whose next_step is null.
    """
    rows = db.execute(
        select(MarketOpportunity, Account)
        .join(Account, Account.id == MarketOpportunity.account_id)
        .where(MarketOpportunity.deleted_at.is_(None))
        .where(MarketOpportunity.stage.in_(("exploring", "active")))
        .where(MarketOpportunity.next_step.is_(None))
    ).all()
    out: list[ActionItem] = []
    for opp, acct in rows:
        out.append(
            ActionItem(
                id=f"market.no_next_step.{opp.id}",
                domain="market",
                kind="market_opportunity_missing_next_step",
                title=f"Set next step: {opp.name}",
                description=(
                    f"Account: {acct.name}. Active opportunity without a next step."
                ),
                priority_score=45,
                status=opp.stage,
                related_entity_type="market_opportunity",
                related_entity_id=opp.id,
                source_label="Market · missing next step",
                link_hint="/market",
            )
        )
    return out


def _actions_program_overdue(db: Session) -> list[ActionItem]:
    now = _now()
    rows = program_service.list_overdue_programs(db, limit=200)
    out: list[ActionItem] = []
    for p in rows:
        days_overdue = max(0, _days_between(p.next_step_due_at, now) or 0)
        out.append(
            ActionItem(
                id=f"program.overdue.{p.id}",
                domain="program",
                kind="program_overdue_next_step",
                title=f"Drive program: {p.name}",
                description=p.next_step or "Next step missing.",
                priority_score=_clip(75 + days_overdue * 2),
                due_at=p.next_step_due_at,
                status=p.stage,
                related_entity_type="program",
                related_entity_id=p.id,
                source_label="Program · overdue",
                link_hint="/programs",
            )
        )
    return out


def _active_programs_without_suppliers(db: Session) -> list[Program]:
    """High-value/active programs with zero program_suppliers entries."""
    rows = program_service.list_high_value_programs(db, limit=100)
    if not rows:
        return []
    program_ids = [p.id for p in rows]
    linked_ids = {
        r.program_id
        for r in db.execute(
            select(ProgramSupplier.program_id).where(
                ProgramSupplier.program_id.in_(program_ids)
            )
        ).all()
    }
    return [p for p in rows if p.id not in linked_ids]


def _actions_program_needs_supplier(db: Session) -> list[ActionItem]:
    rows = _active_programs_without_suppliers(db)
    out: list[ActionItem] = []
    for p in rows:
        out.append(
            ActionItem(
                id=f"program.needs_supplier.{p.id}",
                domain="program",
                kind="program_missing_supplier",
                title=f"Assign suppliers: {p.name}",
                description=(
                    "High-value program has no suppliers linked; delivery risk."
                ),
                priority_score=72,
                status=p.stage,
                related_entity_type="program",
                related_entity_id=p.id,
                source_label="Program · unstaffed",
                link_hint="/programs",
            )
        )
    return out


def _actions_supplier_onboarding(db: Session) -> list[ActionItem]:
    rows = supplier_service.list_suppliers(
        db, onboarding_status="contacted", limit=200
    )
    out: list[ActionItem] = []
    for s in rows:
        out.append(
            ActionItem(
                id=f"supplier.onboarding.{s.id}",
                domain="supplier",
                kind="supplier_onboarding_stalled",
                title=f"Advance onboarding: {s.name}",
                description="Supplier contacted but not yet qualified.",
                priority_score=45,
                status=s.onboarding_status,
                related_entity_type="supplier",
                related_entity_id=s.id,
                source_label="Supplier · onboarding",
                link_hint="/suppliers",
            )
        )
    return out


def _actions_engine_writes(db: Session) -> list[ActionItem]:
    rows = db.execute(
        select(PendingEngineWrite)
        .where(PendingEngineWrite.status.in_((STATUS_FAILED, STATUS_PENDING)))
        .order_by(PendingEngineWrite.created_at.asc())
    ).scalars().all()
    out: list[ActionItem] = []
    for r in rows:
        base = 85 if r.status == STATUS_FAILED else 55
        out.append(
            ActionItem(
                id=f"engine.{r.status}.{r.id}",
                domain="engine",
                kind=f"engine_write_{r.status}",
                title=f"Engine write {r.status}: {r.action_type} ({r.external_id})",
                description=r.last_error or "Queued for the engine worker.",
                priority_score=base,
                status=r.status,
                related_entity_type="pending_engine_write",
                related_entity_id=r.id,
                source_label="Engine · writes",
                link_hint="/engine-writes",
            )
        )
    return out


_REC_TYPE_TO_DOMAIN: dict[str, str] = {
    "investor_for_program": "capital",
    "supplier_for_program": "supplier",
    "account_to_pursue": "market",
    "program_at_risk_no_supplier": "program",
    "program_at_risk_no_investor": "program",
    "cross_domain_opportunity": "program",
}


def _actions_graph_recommendations(db: Session) -> list[ActionItem]:
    """Surface graph recommendations as unified action-queue items.

    Confidence score translates directly to ``priority_score``; the graph
    service already emits structured IDs, reasoning, and link hints, so
    the adapter is mostly identity-mapping.
    """
    bundle = recommendations_service.build_recommendations(db, limit=200)
    out: list[ActionItem] = []
    for rec in bundle.recommendations:
        domain = _REC_TYPE_TO_DOMAIN.get(rec.type, "program")
        primary = rec.related_entities[0] if rec.related_entities else None
        out.append(
            ActionItem(
                id=rec.id,
                domain=domain,  # type: ignore[arg-type]
                kind=f"graph.{rec.type}",
                title=rec.headline,
                description=rec.reasoning,
                priority_score=_clip(rec.confidence_score),
                status="recommended",
                related_entity_type=primary.type if primary else None,
                related_entity_id=primary.id if primary else None,
                source_label=f"Graph · {rec.type}",
                link_hint=rec.link_hint,
            )
        )
    return out


def build_action_queue(
    db: Session, *, limit: int = 50
) -> ActionQueue:
    collected: list[ActionItem] = []
    collected.extend(_actions_investor_overdue(db))
    collected.extend(_actions_investor_missing(db))
    collected.extend(_actions_investor_stale(db))
    collected.extend(_actions_pending_approvals(db))
    collected.extend(_actions_market_follow_ups(db))
    collected.extend(_actions_market_accounts_no_next_step(db))
    collected.extend(_actions_program_overdue(db))
    collected.extend(_actions_program_needs_supplier(db))
    collected.extend(_actions_supplier_onboarding(db))
    collected.extend(_actions_engine_writes(db))
    collected.extend(_actions_graph_recommendations(db))

    # Dedupe by id — graph and native rules sometimes arrive at the same
    # finding (e.g. program_missing_supplier). Prefer the first producer.
    seen: set[str] = set()
    unique: list[ActionItem] = []
    for item in collected:
        if item.id in seen:
            continue
        seen.add(item.id)
        unique.append(item)
    collected = unique

    collected.sort(key=lambda a: (-a.priority_score, a.due_at or _now()))

    counts: dict[str, int] = {}
    for a in collected:
        counts[a.domain] = counts.get(a.domain, 0) + 1

    return ActionQueue(
        generated_at=_now(),
        total=len(collected),
        counts_by_domain=counts,
        items=collected[:limit],
    )


# ---------------------------------------------------------------------------
# alerts
# ---------------------------------------------------------------------------


def _alert_high_value_program_no_supplier(db: Session) -> list[Alert]:
    rows = _active_programs_without_suppliers(db)
    return [
        Alert(
            id=f"alert.program.no_supplier.{p.id}",
            severity="critical",
            domain="program",
            title=f"High-value program has no supplier: {p.name}",
            description=(
                f"Program is in stage '{p.stage}' with no supplier linked. "
                "Delivery capacity is unassigned."
            ),
            related_entity_type="program",
            related_entity_id=p.id,
            recommended_action=(
                "Link at least one qualified supplier via /program-suppliers."
            ),
            link_hint="/programs",
        )
        for p in rows
    ]


def _alert_active_account_no_next_step(db: Session) -> list[Alert]:
    rows = db.execute(
        select(MarketOpportunity, Account)
        .join(Account, Account.id == MarketOpportunity.account_id)
        .where(MarketOpportunity.deleted_at.is_(None))
        .where(MarketOpportunity.stage.in_(("exploring", "active")))
        .where(MarketOpportunity.next_step.is_(None))
    ).all()
    return [
        Alert(
            id=f"alert.market.no_next_step.{opp.id}",
            severity="warn",
            domain="market",
            title=f"Active opportunity '{opp.name}' has no next step",
            description=(
                f"Account {acct.name} · stage {opp.stage}. Will drift without action."
            ),
            related_entity_type="market_opportunity",
            related_entity_id=opp.id,
            recommended_action="Set next_step and next_step_due_at.",
            link_hint="/market",
        )
        for opp, acct in rows
    ]


def _alert_diligence_investor_stale(db: Session) -> list[Alert]:
    summaries = pipeline_service.list_stale_summaries(db)
    alerts: list[Alert] = []
    for opp in summaries:
        if opp.stage and opp.stage.lower() in DILIGENCE_STAGE_NAMES:
            alerts.append(
                Alert(
                    id=f"alert.capital.diligence_stale.{opp.id}",
                    severity="critical",
                    domain="capital",
                    title=(
                        f"Diligence investor is stale: {opp.firm_name or f'opp #{opp.id}'}"
                    ),
                    description=(
                        f"{opp.days_since_last_interaction or 'unknown'} day(s) since "
                        "last interaction while in diligence."
                    ),
                    related_entity_type="investor_opportunity",
                    related_entity_id=opp.id,
                    recommended_action=(
                        "Reach out today; in-flight diligence rots fast."
                    ),
                    link_hint=(
                        f"/investors/{opp.firm_id}" if opp.firm_id else None
                    ),
                )
            )
    return alerts


def _alert_supplier_missing_certification(db: Session) -> list[Alert]:
    """Suppliers linked to active programs but with no active certifications."""
    # suppliers that have at least one active program link
    linked = db.execute(
        select(ProgramSupplier.supplier_id, Program.stage)
        .join(Program, Program.id == ProgramSupplier.program_id)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(("pursuing", "active")))
    ).all()
    if not linked:
        return []
    supplier_ids = {sid for sid, _ in linked}
    active_cert_ids = {
        sid
        for sid in db.execute(
            select(SupplierCertification.supplier_id)
            .where(SupplierCertification.supplier_id.in_(supplier_ids))
            .where(SupplierCertification.status == "active")
        ).scalars().all()
    }
    missing = supplier_ids - active_cert_ids
    if not missing:
        return []
    suppliers = db.execute(
        select(Supplier).where(Supplier.id.in_(missing))
    ).scalars().all()
    return [
        Alert(
            id=f"alert.supplier.no_cert.{s.id}",
            severity="critical",
            domain="supplier",
            title=f"Supplier on active program lacks active certification: {s.name}",
            description=(
                "Supplier is staffed on a pursuing/active program but has no "
                "active certification on file. Program exposure risk."
            ),
            related_entity_type="supplier",
            related_entity_id=s.id,
            recommended_action="Record/refresh AS9100, NADCAP, or ITAR certification.",
            link_hint="/suppliers",
        )
        for s in suppliers
    ]


def _alert_pending_approval_stale(db: Session) -> list[Alert]:
    now = _now()
    threshold = now - timedelta(hours=PENDING_APPROVAL_STALE_HOURS)
    rows = db.execute(
        select(Approval)
        .where(Approval.status == "pending")
        .where(Approval.created_at < threshold)
    ).scalars().all()
    return [
        Alert(
            id=f"alert.approval.stale.{a.id}",
            severity="warn",
            domain="approval",
            title=f"Pending approval > {PENDING_APPROVAL_STALE_HOURS}h: #{a.id}",
            description=(
                f"{a.action} on {a.entity_type} #{a.entity_id} — "
                f"requested by {a.requested_by or 'unknown'}."
            ),
            related_entity_type=a.entity_type,
            related_entity_id=a.entity_id,
            recommended_action="Approve or reject in /approvals.",
            link_hint="/approvals",
        )
        for a in rows
    ]


def _alert_engine_write_failed(db: Session) -> list[Alert]:
    rows = db.execute(
        select(PendingEngineWrite)
        .where(PendingEngineWrite.status == STATUS_FAILED)
    ).scalars().all()
    return [
        Alert(
            id=f"alert.engine.failed.{r.id}",
            severity="critical",
            domain="engine",
            title=f"Engine write failed: {r.action_type} ({r.external_id})",
            description=r.last_error or "No error recorded.",
            related_entity_type="pending_engine_write",
            related_entity_id=r.id,
            recommended_action="Re-trigger from /engine-writes or re-approve.",
            link_hint="/engine-writes",
        )
        for r in rows
    ]


_SEVERITY_ORDER = {"critical": 0, "warn": 1, "info": 2}


def build_alerts(db: Session) -> AlertBundle:
    alerts: list[Alert] = []
    alerts.extend(_alert_high_value_program_no_supplier(db))
    alerts.extend(_alert_active_account_no_next_step(db))
    alerts.extend(_alert_diligence_investor_stale(db))
    alerts.extend(_alert_supplier_missing_certification(db))
    alerts.extend(_alert_pending_approval_stale(db))
    alerts.extend(_alert_engine_write_failed(db))

    alerts.sort(key=lambda a: (_SEVERITY_ORDER.get(a.severity, 99), a.domain))

    counts: dict[str, int] = {}
    for a in alerts:
        counts[a.severity] = counts.get(a.severity, 0) + 1

    return AlertBundle(
        generated_at=_now(),
        total=len(alerts),
        counts_by_severity=counts,
        alerts=alerts,
    )


# ---------------------------------------------------------------------------
# daily briefing
# ---------------------------------------------------------------------------


def _metrics(db: Session) -> ExecutiveMetrics:
    # Capital
    capital_summary = agent_service.build_agent_pipeline_summary(db)
    pending_approvals = db.execute(
        select(Approval).where(Approval.status == "pending")
    ).scalars().all()

    # Market
    market_summary = market_service.dashboard_summary(db)

    # Programs
    program_summary = program_service.pipeline_summary(db)

    # Suppliers
    supplier_summary = supplier_service.onboarding_summary(db)

    # Engine writes
    engine_writes_pending = int(
        db.execute(
            select(PendingEngineWrite).where(
                PendingEngineWrite.status == STATUS_PENDING
            )
        ).scalars().all().__len__()
    )
    engine_writes_failed = int(
        db.execute(
            select(PendingEngineWrite).where(
                PendingEngineWrite.status == STATUS_FAILED
            )
        ).scalars().all().__len__()
    )

    return ExecutiveMetrics(
        capital_active=capital_summary.total_active,
        capital_overdue=capital_summary.overdue_follow_up_count,
        capital_stale=capital_summary.stale_count,
        capital_pending_approvals=len(pending_approvals),
        market_accounts=market_summary.get("total_accounts", 0),
        market_active_campaigns=market_summary.get("active_campaigns", 0),
        market_active_opportunities=market_summary.get(
            "active_opportunities", 0
        ),
        market_follow_ups_due=market_summary.get(
            "accounts_needing_follow_up", 0
        ),
        programs_active=program_summary["active_count"],
        programs_high_value=program_summary["high_value_count"],
        programs_overdue=program_summary["overdue_count"],
        suppliers_total=supplier_summary["total"],
        suppliers_qualified=supplier_summary["qualified"],
        suppliers_onboarded=supplier_summary["onboarded"],
        engine_writes_pending=engine_writes_pending,
        engine_writes_failed=engine_writes_failed,
    )


def _section_capital(db: Session) -> BriefingSection:
    summary = agent_service.build_agent_pipeline_summary(db)
    priorities = summary.top_priority[:5]
    items = [
        BriefingItem(
            label=o.firm_name or f"opportunity #{o.id}",
            subtitle=o.stage,
            badge=f"p{o.priority_score}" if o.priority_score is not None else None,
            related_entity_type="investor_opportunity",
            related_entity_id=o.id,
            link_hint=f"/investors/{o.firm_id}" if o.firm_id else None,
        )
        for o in priorities
    ]
    return BriefingSection(
        domain="capital",
        title="Investor priorities",
        headline=(
            f"{summary.total_active} active · {summary.overdue_follow_up_count} overdue "
            f"· {summary.stale_count} stale"
        ),
        count=summary.total_active,
        items=items,
    )


def _section_capital_overdue(db: Session) -> BriefingSection:
    rows = pipeline_service.list_overdue_summaries(db)[:5]
    items = [
        BriefingItem(
            label=o.firm_name or f"opportunity #{o.id}",
            subtitle=f"due {o.next_step_due_at.isoformat() if o.next_step_due_at else '—'}",
            badge="overdue",
            related_entity_type="investor_opportunity",
            related_entity_id=o.id,
            link_hint=f"/investors/{o.firm_id}" if o.firm_id else None,
        )
        for o in rows
    ]
    return BriefingSection(
        domain="capital",
        title="Overdue investor follow-ups",
        headline=f"{len(rows)} overdue follow-up(s)",
        count=len(rows),
        items=items,
    )


def _section_market(db: Session) -> BriefingSection:
    opps = market_service.list_active_opportunities(db, limit=5)
    items = [
        BriefingItem(
            label=o.name,
            subtitle=o.account.name if o.account else None,
            badge=o.stage,
            related_entity_type="market_opportunity",
            related_entity_id=o.id,
            link_hint="/market",
        )
        for o in opps
    ]
    return BriefingSection(
        domain="market",
        title="Active market opportunities",
        headline=f"{len(opps)} active opportunit(ies) surfaced",
        count=len(opps),
        items=items,
    )


def _section_market_follow_ups(db: Session) -> BriefingSection:
    rows = market_service.accounts_needing_follow_up(db, limit=5)
    items = [
        BriefingItem(
            label=(link.account.name if link.account else f"account #{link.account_id}"),
            subtitle=(
                link.campaign.name if link.campaign else f"campaign #{link.campaign_id}"
            ),
            badge=link.status,
            related_entity_type="account_campaign",
            related_entity_id=link.id,
            link_hint="/market",
        )
        for link in rows
    ]
    return BriefingSection(
        domain="market",
        title="Accounts needing follow-up",
        headline=f"{len(rows)} account/campaign pair(s) due",
        count=len(rows),
        items=items,
    )


def _section_programs(db: Session) -> BriefingSection:
    active = program_service.list_active_programs(db, limit=5)
    items = [
        BriefingItem(
            label=p.name,
            subtitle=p.owner or "unassigned",
            badge=p.stage,
            related_entity_type="program",
            related_entity_id=p.id,
            link_hint="/programs",
        )
        for p in active
    ]
    return BriefingSection(
        domain="program",
        title="Active programs",
        headline=f"{len(active)} active program(s)",
        count=len(active),
        items=items,
    )


def _section_programs_overdue(db: Session) -> BriefingSection:
    overdue = program_service.list_overdue_programs(db, limit=5)
    items = [
        BriefingItem(
            label=p.name,
            subtitle=p.next_step or "no next step",
            badge="overdue",
            related_entity_type="program",
            related_entity_id=p.id,
            link_hint="/programs",
        )
        for p in overdue
    ]
    return BriefingSection(
        domain="program",
        title="Overdue program next steps",
        headline=f"{len(overdue)} program(s) with overdue next steps",
        count=len(overdue),
        items=items,
    )


def _section_suppliers_onboarding(db: Session) -> BriefingSection:
    data = supplier_service.onboarding_summary(db)
    contacted = supplier_service.list_suppliers(
        db, onboarding_status="contacted", limit=5
    )
    items = [
        BriefingItem(
            label=s.name,
            subtitle=s.type or s.region or "—",
            badge=s.onboarding_status,
            related_entity_type="supplier",
            related_entity_id=s.id,
            link_hint="/suppliers",
        )
        for s in contacted
    ]
    return BriefingSection(
        domain="supplier",
        title="Supplier onboarding gaps",
        headline=(
            f"{data['qualified']} qualified · {data['onboarded']} onboarded · "
            f"{data['active_program_supplier_count']} on active programs"
        ),
        count=len(contacted),
        items=items,
    )


def _section_suppliers_on_programs(db: Session) -> BriefingSection:
    rows = db.execute(
        select(ProgramSupplier, Program, Supplier)
        .join(Program, Program.id == ProgramSupplier.program_id)
        .join(Supplier, Supplier.id == ProgramSupplier.supplier_id)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(("pursuing", "active")))
        .limit(5)
    ).all()
    items = [
        BriefingItem(
            label=sup.name,
            subtitle=f"on {prog.name} · {ps.role}",
            badge=ps.status,
            related_entity_type="program_supplier",
            related_entity_id=ps.id,
            link_hint="/suppliers",
        )
        for ps, prog, sup in rows
    ]
    return BriefingSection(
        domain="supplier",
        title="Suppliers on active programs",
        headline=f"{len(rows)} supplier/program link(s)",
        count=len(rows),
        items=items,
    )


def _section_graph_recommendations(db: Session) -> BriefingSection:
    bundle = recommendations_service.build_recommendations(db, limit=5)
    items = [
        BriefingItem(
            label=r.headline,
            subtitle=r.recommended_action,
            badge=f"c{r.confidence_score}",
            related_entity_type=(
                r.related_entities[0].type if r.related_entities else None
            ),
            related_entity_id=(
                r.related_entities[0].id if r.related_entities else None
            ),
            link_hint=r.link_hint,
        )
        for r in bundle.recommendations
    ]
    return BriefingSection(
        domain="program",
        title="Cross-domain recommendations",
        headline=(
            f"{bundle.total} graph recommendation(s) "
            f"across {len(bundle.counts_by_type)} type(s)"
        ),
        count=bundle.total,
        items=items,
    )


def _section_approvals(db: Session) -> BriefingSection:
    rows = db.execute(
        select(Approval)
        .where(Approval.status == "pending")
        .order_by(Approval.created_at.asc())
        .limit(5)
    ).scalars().all()
    items = [
        BriefingItem(
            label=f"#{a.id} · {a.action}",
            subtitle=f"{a.entity_type} #{a.entity_id}",
            badge=a.status,
            related_entity_type=a.entity_type,
            related_entity_id=a.entity_id,
            link_hint="/approvals",
        )
        for a in rows
    ]
    return BriefingSection(
        domain="approval",
        title="Pending approvals",
        headline=f"{len(rows)} approval(s) awaiting review",
        count=len(rows),
        items=items,
    )


def _section_engine_writes(db: Session) -> BriefingSection:
    rows = db.execute(
        select(PendingEngineWrite)
        .where(PendingEngineWrite.status.in_((STATUS_PENDING, STATUS_FAILED)))
        .order_by(PendingEngineWrite.created_at.asc())
        .limit(5)
    ).scalars().all()
    items = [
        BriefingItem(
            label=f"{r.action_type} → {r.external_id}",
            subtitle=r.last_error or None,
            badge=r.status,
            related_entity_type="pending_engine_write",
            related_entity_id=r.id,
            link_hint="/engine-writes",
        )
        for r in rows
    ]
    return BriefingSection(
        domain="engine",
        title="Investor engine writes",
        headline=f"{len(rows)} pending/failed write(s)",
        count=len(rows),
        items=items,
    )


def _narrative(
    metrics: ExecutiveMetrics,
    alerts: AlertBundle,
    queue: ActionQueue,
) -> list[str]:
    out: list[str] = []
    if queue.total == 0 and alerts.total == 0:
        out.append("No outstanding actions or alerts across the system.")
        return out

    critical = alerts.counts_by_severity.get("critical", 0)
    warn = alerts.counts_by_severity.get("warn", 0)
    if critical:
        out.append(f"{critical} critical alert(s) — address today.")
    if warn:
        out.append(f"{warn} warning alert(s) queued.")

    if metrics.capital_overdue:
        out.append(
            f"Capital: {metrics.capital_overdue} overdue investor follow-up(s), "
            f"{metrics.capital_stale} stale."
        )
    if metrics.market_follow_ups_due:
        out.append(
            f"Market: {metrics.market_follow_ups_due} account/campaign follow-up(s) due."
        )
    if metrics.programs_overdue:
        out.append(
            f"Programs: {metrics.programs_overdue} program(s) with overdue next steps."
        )
    if metrics.engine_writes_failed:
        out.append(
            f"Engine: {metrics.engine_writes_failed} failed write(s) need re-approval."
        )
    if metrics.capital_pending_approvals:
        out.append(
            f"Approvals: {metrics.capital_pending_approvals} pending review."
        )
    return out


def build_briefing(db: Session) -> DailyBriefing:
    now = _now()
    metrics = _metrics(db)
    queue = build_action_queue(db, limit=200)
    alerts = build_alerts(db)

    sections = [
        _section_capital(db),
        _section_capital_overdue(db),
        _section_market(db),
        _section_market_follow_ups(db),
        _section_programs(db),
        _section_programs_overdue(db),
        _section_suppliers_onboarding(db),
        _section_suppliers_on_programs(db),
        _section_graph_recommendations(db),
        _section_approvals(db),
        _section_engine_writes(db),
    ]

    headline = (
        f"{queue.total} action(s) · {alerts.counts_by_severity.get('critical', 0)} "
        f"critical alert(s) · {metrics.programs_active} active program(s)."
    )

    return DailyBriefing(
        generated_at=now,
        headline=headline,
        narrative=_narrative(metrics, alerts, queue),
        metrics=metrics,
        sections=sections,
        top_actions=queue.items[:10],
        top_risks=[a for a in alerts.alerts if a.severity == "critical"][:10]
        or alerts.alerts[:10],
    )
