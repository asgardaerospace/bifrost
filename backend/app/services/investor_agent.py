"""Investor Agent application layer.

Reuses deterministic services (pipeline, timeline, communications) and adds
concise narrative/rationale text suitable for UI or command-console use.

LLM generation is intentionally isolated behind ``_narrative`` helpers so a
future provider can replace them without changing aggregation logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.investor import InvestorContact, InvestorFirm
from app.schemas.investor_agent import (
    AgentFollowUpDraftRequest,
    AgentFollowUpDraftResponse,
    AgentPipelineSummary,
    InvestorBrief,
    PrioritizedOpportunitiesResponse,
    PrioritizedOpportunity,
    TimelineHighlight,
)
from app.schemas.pipeline import OpportunitySummary
from app.schemas.workflows import FollowUpDraftRequest
from app.services import communications as communications_service
from app.services import investor as investor_service
from app.services import pipeline as pipeline_service
from app.services import timeline as timeline_service


# ---------------------------------------------------------------------------
# pipeline summary
# ---------------------------------------------------------------------------

def _pipeline_narrative(summary) -> str:
    if summary.total_active == 0:
        return "No active investor opportunities in the pipeline."
    parts = [f"{summary.total_active} active opportunities."]
    if summary.overdue_follow_up_count:
        parts.append(f"{summary.overdue_follow_up_count} overdue follow-up(s).")
    if summary.missing_next_step_count:
        parts.append(
            f"{summary.missing_next_step_count} missing a defined next step."
        )
    if summary.stale_count:
        parts.append(
            f"{summary.stale_count} stale (>{summary.stale_threshold_days}d since last interaction)."
        )
    if summary.top_priority:
        top = summary.top_priority[0]
        label = top.firm_name or f"opp #{top.id}"
        parts.append(f"Top priority: {label} (stage '{top.stage}').")
    return " ".join(parts)


def build_agent_pipeline_summary(
    db: Session,
    *,
    stale_threshold_days: int = pipeline_service.DEFAULT_STALE_DAYS,
    top_priority_limit: int = pipeline_service.DEFAULT_TOP_PRIORITY,
) -> AgentPipelineSummary:
    summary = pipeline_service.build_pipeline_summary(
        db,
        stale_threshold_days=stale_threshold_days,
        top_priority_limit=top_priority_limit,
    )
    return AgentPipelineSummary.from_pipeline(
        summary, narrative=_pipeline_narrative(summary)
    )


# ---------------------------------------------------------------------------
# prioritization
# ---------------------------------------------------------------------------

def _recommended_next_action(opp: OpportunitySummary, now: datetime) -> str:
    if not (opp.next_step and opp.next_step.strip()):
        return "Define the next step for this opportunity."
    if opp.next_step_due_at is not None and opp.next_step_due_at < now:
        days = (now - opp.next_step_due_at).days
        return (
            f"Follow up (overdue {days}d): {opp.next_step.strip()}"
        )
    if opp.days_since_last_interaction is not None and opp.days_since_last_interaction > 21:
        return (
            f"Re-engage — {opp.days_since_last_interaction}d since last interaction. "
            f"Execute: {opp.next_step.strip()}"
        )
    return f"Advance per current plan: {opp.next_step.strip()}"


def _rationale_factors(opp: OpportunitySummary, now: datetime) -> list[str]:
    factors: list[str] = [f"stage='{opp.stage}'"]
    if opp.probability_score is not None:
        factors.append(f"probability={opp.probability_score}")
    if opp.strategic_value_score is not None:
        factors.append(f"strategic_value={opp.strategic_value_score}")
    if opp.fit_score is not None:
        factors.append(f"fit={opp.fit_score}")
    if opp.next_step_due_at is not None and opp.next_step_due_at < now:
        factors.append(f"overdue_by={(now - opp.next_step_due_at).days}d")
    if opp.days_since_last_interaction is not None:
        factors.append(f"last_interaction={opp.days_since_last_interaction}d")
    if not (opp.next_step and opp.next_step.strip()):
        factors.append("missing_next_step")
    return factors


def _rationale(opp: OpportunitySummary, factors: list[str]) -> str:
    label = opp.firm_name or f"opportunity #{opp.id}"
    return f"{label}: " + ", ".join(factors) + "."


def prioritize_opportunities(
    db: Session, *, limit: int = 10
) -> PrioritizedOpportunitiesResponse:
    now = datetime.now(timezone.utc)
    summary = pipeline_service.build_pipeline_summary(
        db, top_priority_limit=limit
    )

    results: list[PrioritizedOpportunity] = []
    for opp in summary.top_priority:
        factors = _rationale_factors(opp, now)
        results.append(
            PrioritizedOpportunity(
                opportunity=opp,
                priority_score=opp.priority_score or 0.0,
                rationale=_rationale(opp, factors),
                recommended_next_action=_recommended_next_action(opp, now),
                factors=factors,
            )
        )

    return PrioritizedOpportunitiesResponse(
        count=len(results),
        generated_at=now,
        results=results,
    )


# ---------------------------------------------------------------------------
# investor brief
# ---------------------------------------------------------------------------

def _score_band(value: Optional[int]) -> str:
    if value is None:
        return "not scored"
    if value >= 75:
        return "strong"
    if value >= 50:
        return "moderate"
    if value >= 25:
        return "weak"
    return "very weak"


def _assessment(label: str, value: Optional[int]) -> str:
    return f"{label}: {_score_band(value)}" + (
        f" ({value}/100)" if value is not None else ""
    )


def _collect_blockers(opp, days_since: Optional[int]) -> list[str]:
    blockers: list[str] = []
    if not (opp.next_step and opp.next_step.strip()):
        blockers.append("No next step defined.")
    if opp.next_step_due_at is not None and opp.next_step_due_at < datetime.now(timezone.utc):
        blockers.append("Next step is overdue.")
    if days_since is not None and days_since > 21:
        blockers.append(f"No interaction in {days_since} days.")
    if opp.owner is None:
        blockers.append("No owner assigned.")
    return blockers


def _missing_context(
    firm: Optional[InvestorFirm],
    contact: Optional[InvestorContact],
    opp,
) -> list[str]:
    missing: list[str] = []
    if firm is None or not (firm.description or "").strip():
        missing.append("firm description")
    if contact is None:
        missing.append("primary contact")
    elif not (contact.email or "").strip():
        missing.append("primary contact email")
    if not (opp.summary or "").strip():
        missing.append("opportunity summary")
    return missing


def _executive_focus(opp, blockers: list[str]) -> str:
    if blockers:
        return f"Resolve: {blockers[0]}"
    stage = (opp.stage or "").lower()
    if stage in {"partner_meeting", "term_sheet", "decision"}:
        return "Close-stage — prioritize decision-making pressure and materials."
    if stage in {"diligence"}:
        return "Keep diligence momentum; answer open questions quickly."
    if stage in {"intro_call", "contacted"}:
        return "Deepen engagement and qualify fit."
    return "Advance to the next qualification stage."


def build_investor_brief(db: Session, opportunity_id: int) -> InvestorBrief:
    opp = investor_service.get_opportunity(db, opportunity_id)
    firm = db.get(InvestorFirm, opp.firm_id)

    contact: Optional[InvestorContact] = None
    if opp.primary_contact_id is not None:
        contact = db.get(InvestorContact, opp.primary_contact_id)
        if contact is not None and contact.deleted_at is not None:
            contact = None

    interactions = pipeline_service._last_interaction_map(db, [opp.id])
    last = interactions.get(opp.id)
    now = datetime.now(timezone.utc)
    days_since = (now - last).days if last is not None else None

    timeline = timeline_service.build_opportunity_timeline(
        db, opp.id, limit=10
    )
    highlights = [
        TimelineHighlight(
            occurred_at=i.occurred_at,
            item_type=i.item_type,
            title=i.title,
            summary=i.summary,
        )
        for i in timeline.items[:5]
    ]

    blockers = _collect_blockers(opp, days_since)

    return InvestorBrief(
        opportunity_id=opp.id,
        firm_id=opp.firm_id,
        firm_name=firm.name if firm else None,
        firm_overview=(firm.description if firm else None),
        primary_contact_id=contact.id if contact else None,
        primary_contact_name=contact.name if contact else None,
        primary_contact_email=contact.email if contact else None,
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
        blockers=blockers,
        recent_activity=highlights,
        fit_assessment=_assessment("Fit", opp.fit_score),
        strategic_value_assessment=_assessment(
            "Strategic value", opp.strategic_value_score
        ),
        recommended_executive_focus=_executive_focus(opp, blockers),
        missing_context=_missing_context(firm, contact, opp),
        generated_at=now,
    )


# ---------------------------------------------------------------------------
# follow-up draft orchestration
# ---------------------------------------------------------------------------

def _draft_rationale(
    brief: InvestorBrief, intent: Optional[str]
) -> str:
    parts: list[str] = []
    if intent:
        parts.append(f"Intent: {intent}.")
    parts.append(f"Stage '{brief.stage}'.")
    if brief.days_since_last_interaction is not None:
        parts.append(
            f"Last interaction {brief.days_since_last_interaction}d ago."
        )
    if brief.next_step:
        parts.append(f"Next step on file: {brief.next_step}.")
    if brief.blockers:
        parts.append(f"Open blocker: {brief.blockers[0]}")
    return " ".join(parts)


def orchestrate_follow_up_draft(
    db: Session,
    opportunity_id: int,
    payload: AgentFollowUpDraftRequest,
) -> AgentFollowUpDraftResponse:
    brief = build_investor_brief(db, opportunity_id)

    draft_request = FollowUpDraftRequest(
        contact_id=payload.contact_id,
        subject=payload.subject,
        body=payload.body,
        from_address=payload.from_address,
        to_address=payload.to_address,
        actor=payload.actor,
    )

    communication, workflow_run = communications_service.create_follow_up_draft(
        db, opportunity_id, draft_request
    )

    return AgentFollowUpDraftResponse(
        communication=communication,
        workflow_run=workflow_run,
        rationale=_draft_rationale(brief, payload.intent),
        missing_context=brief.missing_context,
    )
