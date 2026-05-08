"""Executive intelligence synthesis — grounded daily briefing.

Doctrine: leadership receives a calm, source-cited, confidence-scored
synthesis of organizational movement. No hype. No speculative predictions.

Inputs:
  * top decayed-relevance signals across all active missions
  * mission pressure deltas (last 24h)
  * recent operational events of severity warning|critical
  * mission-impact summaries (signal_impact rows aggregated by mission)

Outputs (SynthesisResponse shape from Sprint 3):
  * objective: "Daily executive briefing — <date>"
  * grounded summary with [#k] citations
  * confidence
  * weak_retrieval flag
  * full retrieval trace
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intel import IntelItem
from app.models.mission import Mission
from app.models.signal import SignalImpact, SignalRelevance
from app.services import retrieval as retrieval_service
from app.services.rag import (
    SYSTEM_PROMPT,
    Citation,
    SynthesisResponse,
    _build_prompt,
    _filter_used_citations,
    _format_retrieval_block,
)
from app.services.llm import get_provider as get_llm_provider


def daily_brief(db: Session, *, hours: int = 24) -> SynthesisResponse:
    """Top strategic movement across all active missions, grounded in memory."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Compose the retrieval query from the highest-impact signals so we
    # ground synthesis on actual operational movement rather than a free
    # text query. This is the doctrine-aligned "retrieval before generation"
    # path: structured filter → semantic retrieval → assembly.
    top_relevant = db.scalars(
        select(SignalRelevance)
        .where(SignalRelevance.is_relevant.is_(True))
        .order_by(SignalRelevance.decayed_score.desc())
        .limit(8)
    ).all()
    top_intel_ids = [r.intel_item_id for r in top_relevant]
    top_titles: list[str] = []
    if top_intel_ids:
        rows = db.scalars(
            select(IntelItem).where(IntelItem.id.in_(top_intel_ids))
        ).all()
        top_titles = [r.title for r in rows if r.title]

    query_terms = " ; ".join(top_titles[:5]) or (
        "executive briefing — strategic movement across active missions"
    )

    results, trace = retrieval_service.search(
        db,
        query=query_terms,
        since=since,
        source_types=["intel_item", "approval", "operational_event", "mission"],
        limit=10,
        candidate_limit=400,
    )

    if retrieval_service.is_weak(results):
        return SynthesisResponse(
            objective="Daily executive briefing",
            summary=(
                "INSUFFICIENT CONTEXT — no relevant operational movement in the "
                f"last {hours}h cleared the relevance floor. Skipping synthesis."
            ),
            confidence=0.0,
            weak_retrieval=True,
            citations=[],
            retrieval_trace=trace,
            model=get_llm_provider().name,
        )

    block, citations = _format_retrieval_block(results)
    user_prompt = _build_prompt(
        task=f"Daily executive briefing — last {hours}h",
        instructions=(
            "Produce 4–6 short bullets covering only material strategic movement. "
            "No hype. No speculation. Cluster by domain (procurement, supplier risk, "
            "capital, launch, regulatory) where natural. Cite every claim by [#k]."
        ),
        retrieval_block=block,
    )
    provider = get_llm_provider()
    resp = provider.synthesize(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    used = _filter_used_citations(resp.text, citations)
    return SynthesisResponse(
        objective=f"Daily executive briefing — last {hours}h",
        summary=resp.text,
        confidence=resp.confidence,
        weak_retrieval=False,
        citations=used or citations,
        retrieval_trace=trace,
        model=resp.model,
    )


def mission_impact_summary(
    db: Session, mission_id: int, *, hours: int = 24
) -> SynthesisResponse:
    """Per-mission grounded summary of intelligence impact in the last N hours."""
    mission = db.get(Mission, mission_id)
    if mission is None or mission.deleted_at is not None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Mission #{mission_id} not found")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Mission-scoped impacts → drives the query terms for retrieval.
    impacts = db.scalars(
        select(SignalImpact)
        .where(SignalImpact.mission_id == mission_id)
        .where(SignalImpact.computed_at >= since)
        .order_by(SignalImpact.contribution.desc())
        .limit(10)
    ).all()
    intel_ids = list({imp.intel_item_id for imp in impacts})

    titles: list[str] = []
    if intel_ids:
        titles = [
            i.title
            for i in db.scalars(
                select(IntelItem).where(IntelItem.id.in_(intel_ids))
            ).all()
            if i.title
        ]
    query_terms = (
        " ; ".join(titles[:5])
        or f"intelligence impact on {mission.codename} {mission.name}"
    )

    results, trace = retrieval_service.search(
        db,
        query=query_terms,
        mission_id=mission_id,
        since=since,
        source_types=["intel_item", "operational_event", "approval"],
        limit=8,
    )

    if retrieval_service.is_weak(results):
        return SynthesisResponse(
            objective=f"Intelligence impact on {mission.codename}",
            summary=(
                "INSUFFICIENT CONTEXT — no signals cleared the relevance floor "
                f"for this mission in the last {hours}h."
            ),
            confidence=0.0,
            weak_retrieval=True,
            citations=[],
            retrieval_trace=trace,
            model=get_llm_provider().name,
        )

    block, citations = _format_retrieval_block(results)
    user_prompt = _build_prompt(
        task=f"Intelligence impact on {mission.codename}",
        instructions=(
            "Summarize how recent intelligence has moved this mission's posture. "
            "Bullets only. Cite every claim. No predictions."
        ),
        retrieval_block=block,
    )
    provider = get_llm_provider()
    resp = provider.synthesize(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    used = _filter_used_citations(resp.text, citations)
    return SynthesisResponse(
        objective=f"Intelligence impact on {mission.codename}",
        summary=resp.text,
        confidence=resp.confidence,
        weak_retrieval=False,
        citations=used or citations,
        retrieval_trace=trace,
        model=resp.model,
    )
