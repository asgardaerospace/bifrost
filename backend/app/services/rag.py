"""Retrieval-Augmented Generation pipeline.

Doctrine non-negotiables:
  * Retrieval before generation, always.
  * Every synthesized response cites the chunks it was grounded in.
  * Confidence + retrieval trace are exposed on every response.
  * Weak retrieval triggers `weak_retrieval=True` and a graceful refusal —
    AI may not fabricate operational state.

Pipeline:
    structured filter (mission/entity/temporal)
        → semantic + keyword + recency retrieval
        → graph context expansion (mission relationships + linked entities)
        → prompt assembly with [#k] citation markers
        → LLM synthesis (local or anthropic)
        → citation extraction + confidence reporting
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mission import Mission
from app.services import retrieval as retrieval_service
from app.services.llm import get_provider as get_llm_provider
from app.services.retrieval import RetrievalResult, RetrievalTrace


_CITATION_RE = re.compile(r"\[#(\d+)\]")


# ---------------------------------------------------------------------------
# response shapes
# ---------------------------------------------------------------------------


@dataclass
class Citation:
    marker: str  # "[#1]" etc.
    chunk_id: int
    record_id: int
    source_type: str
    source_id: int
    title: Optional[str]
    excerpt: str


@dataclass
class SynthesisResponse:
    objective: str
    summary: str
    confidence: float
    weak_retrieval: bool
    citations: List[Citation]
    retrieval_trace: RetrievalTrace
    model: str


# ---------------------------------------------------------------------------
# prompt assembly
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = (
    "You are Bifrost, a grounded operational-cognition layer for Asgard "
    "Aerospace. You may only synthesize from the <retrieved> context "
    "supplied by the user. Cite every claim by the bracketed marker that "
    "introduces each chunk (e.g. [#1]). If the retrieved context is "
    "insufficient, say so explicitly — never fabricate operational state."
)


def _format_retrieval_block(results: List[RetrievalResult]) -> tuple[str, List[Citation]]:
    lines: list[str] = []
    citations: list[Citation] = []
    for i, r in enumerate(results, start=1):
        marker = f"[#{i}]"
        excerpt = r.text.strip()
        if len(excerpt) > 600:
            excerpt = excerpt[:600] + "…"
        lines.append(
            f"{marker} ({r.source_type}#{r.source_id} — {r.title or 'untitled'})\n{excerpt}"
        )
        citations.append(
            Citation(
                marker=marker,
                chunk_id=r.chunk_id,
                record_id=r.record_id,
                source_type=r.source_type,
                source_id=r.source_id,
                title=r.title,
                excerpt=excerpt,
            )
        )
    return "\n\n".join(lines), citations


def _build_prompt(*, task: str, retrieval_block: str, instructions: str) -> str:
    return (
        f"<task>{task}</task>\n\n"
        f"<instructions>{instructions}</instructions>\n\n"
        f"<retrieved>\n{retrieval_block}\n</retrieved>\n\n"
        "Respond in 3-6 short bullets. Every bullet must cite at least one "
        "[#k] marker. If the retrieved context cannot support a grounded "
        "answer, say `INSUFFICIENT CONTEXT` and stop."
    )


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------


def _filter_used_citations(
    text: str, all_citations: List[Citation]
) -> List[Citation]:
    used = {m.group(0) for m in _CITATION_RE.finditer(text)}
    return [c for c in all_citations if c.marker in used]


# ---------------------------------------------------------------------------
# entrypoints
# ---------------------------------------------------------------------------


def _synthesize(
    *,
    objective: str,
    instructions: str,
    results: List[RetrievalResult],
    trace: RetrievalTrace,
) -> SynthesisResponse:
    if retrieval_service.is_weak(results):
        return SynthesisResponse(
            objective=objective,
            summary=(
                "INSUFFICIENT CONTEXT — retrieval did not return chunks above "
                "the relevance threshold for this query. No synthesis "
                "produced. Tighten scope or extend the temporal window."
            ),
            confidence=0.0,
            weak_retrieval=True,
            citations=[],
            retrieval_trace=trace,
            model=get_llm_provider().name,
        )

    block, citations = _format_retrieval_block(results)
    user_prompt = _build_prompt(
        task=objective,
        instructions=instructions,
        retrieval_block=block,
    )
    provider = get_llm_provider()
    resp = provider.synthesize(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    used = _filter_used_citations(resp.text, citations)
    return SynthesisResponse(
        objective=objective,
        summary=resp.text,
        confidence=resp.confidence,
        weak_retrieval=False,
        citations=used or citations,  # never return empty when LLM omitted markers
        retrieval_trace=trace,
        model=resp.model,
    )


def summarize_mission(db: Session, mission_id: int) -> SynthesisResponse:
    """High-level mission state summary grounded in mission + recent events."""
    mission = db.get(Mission, mission_id)
    if mission is None or mission.deleted_at is not None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Mission #{mission_id} not found")
    query = (
        f"Mission {mission.codename} {mission.name} — current operational "
        f"state, blockers, approvals, recent activity."
    )
    results, trace = retrieval_service.search(
        db,
        query=query,
        mission_id=mission_id,
        limit=8,
    )
    return _synthesize(
        objective=f"Summarize mission {mission.codename}",
        instructions=(
            "Capture: (a) what this mission is, (b) current health and "
            "pressure drivers, (c) outstanding blockers or approvals, "
            "(d) most recent operational movement."
        ),
        results=results,
        trace=trace,
    )


def explain_pressure(db: Session, mission_id: int) -> SynthesisResponse:
    """Synthesize the dominant pressure drivers for a mission."""
    mission = db.get(Mission, mission_id)
    if mission is None or mission.deleted_at is not None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Mission #{mission_id} not found")
    query = (
        f"What is driving pressure on mission {mission.codename}? Blockers, "
        "overdue items, pending approvals, escalations, intel."
    )
    results, trace = retrieval_service.search(
        db,
        query=query,
        mission_id=mission_id,
        limit=10,
        source_types=[
            "operational_event",
            "execution_queue_item",
            "approval",
            "intel_item",
        ],
    )
    return _synthesize(
        objective=f"Explain pressure drivers for {mission.codename}",
        instructions=(
            "List the specific signals contributing to current pressure. "
            "Group by category (blocker, overdue, approval, escalation). "
            "Each bullet should cite the source chunks that evidence the claim."
        ),
        results=results,
        trace=trace,
    )


def synthesize_history(
    db: Session, mission_id: int, *, days: int = 14
) -> SynthesisResponse:
    """Walk the mission's recent history, grounded in the operational record."""
    mission = db.get(Mission, mission_id)
    if mission is None or mission.deleted_at is not None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Mission #{mission_id} not found")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = (
        f"Operational history for mission {mission.codename} over the last "
        f"{days} days — what changed, what was approved, what was blocked."
    )
    results, trace = retrieval_service.search(
        db,
        query=query,
        mission_id=mission_id,
        since=since,
        limit=10,
    )
    return _synthesize(
        objective=f"Synthesize {days}-day history for {mission.codename}",
        instructions=(
            "Reconstruct the timeline of operational events and decisions in "
            "chronological order. Highlight inflection points (status "
            "changes, approval events, escalations). Cite every claim."
        ),
        results=results,
        trace=trace,
    )


def find_related_missions(
    db: Session, mission_id: int, *, limit: int = 6
) -> tuple[list[dict], RetrievalTrace]:
    """Retrieve mission-typed records similar to the given mission's content,
    excluding itself. Used by the 'similar missions' / 'recurring blockers'
    UI surfaces — pure retrieval, no LLM synthesis."""
    mission = db.get(Mission, mission_id)
    if mission is None or mission.deleted_at is not None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Mission #{mission_id} not found")
    query = (
        f"{mission.codename} {mission.name} {mission.description or ''} "
        f"{mission.mission_type} {mission.priority}"
    )
    results, trace = retrieval_service.search(
        db,
        query=query,
        source_types=["mission"],
        limit=limit + 1,  # +1 in case the mission itself comes back top
    )
    related: list[dict] = []
    for r in results:
        if r.source_type == "mission" and r.source_id == mission_id:
            continue
        related.append(
            {
                "mission_id": r.source_id,
                "title": r.title,
                "score": r.score,
                "components": r.components,
                "excerpt": r.text[:200],
            }
        )
        if len(related) >= limit:
            break
    return related, trace
