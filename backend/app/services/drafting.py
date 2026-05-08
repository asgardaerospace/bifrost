"""AI drafting helpers — grounded, editable, never auto-sent.

Doctrine: AI may draft. AI may not send communications, mutate state,
approve workflows, or trigger escalations automatically. Every draft is
returned to the operator for review + manual action.

Each draft is built by:
  1. structured retrieval over relevant memory (mission-scoped where it
     makes sense; entity-scoped for opp/supplier drafts)
  2. assembly into a per-template prompt with [#k] citation markers
  3. LLM synthesis (local-deterministic-v1 default; anthropic via env)
  4. citation extraction for the operator's audit
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.investor import InvestorOpportunity
from app.models.mission import Mission
from app.services import retrieval as retrieval_service
from app.services.llm import get_provider as get_llm_provider
from app.services.rag import (
    SYSTEM_PROMPT,
    SynthesisResponse,
    _build_prompt,
    _filter_used_citations,
    _format_retrieval_block,
)


def _synthesize(
    db: Session,
    *,
    objective: str,
    instructions: str,
    query: str,
    mission_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    source_types: Optional[list[str]] = None,
    since: Optional[datetime] = None,
    limit: int = 8,
) -> SynthesisResponse:
    results, trace = retrieval_service.search(
        db,
        query=query,
        mission_id=mission_id,
        entity_type=entity_type,
        entity_id=entity_id,
        source_types=source_types,
        since=since,
        limit=limit,
    )
    if retrieval_service.is_weak(results):
        return SynthesisResponse(
            objective=objective,
            summary=(
                "INSUFFICIENT CONTEXT — drafting requires more grounded "
                "operational context than retrieval returned. Capture additional "
                "notes / intelligence and retry."
            ),
            confidence=0.0,
            weak_retrieval=True,
            citations=[],
            retrieval_trace=trace,
            model=get_llm_provider().name,
        )
    block, citations = _format_retrieval_block(results)
    user_prompt = _build_prompt(
        task=objective, instructions=instructions, retrieval_block=block
    )
    provider = get_llm_provider()
    resp = provider.synthesize(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    used = _filter_used_citations(resp.text, citations)
    return SynthesisResponse(
        objective=objective,
        summary=resp.text,
        confidence=resp.confidence,
        weak_retrieval=False,
        citations=used or citations,
        retrieval_trace=trace,
        model=resp.model,
    )


# ---------------------------------------------------------------------------
# templates
# ---------------------------------------------------------------------------


def executive_summary_draft(db: Session, mission_id: int) -> SynthesisResponse:
    mission = db.get(Mission, mission_id)
    if mission is None or mission.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Mission #{mission_id} not found")
    return _synthesize(
        db,
        objective=f"Executive summary draft — {mission.codename}",
        instructions=(
            "Draft a 4-6 bullet executive summary covering current status, "
            "pressure drivers, blockers, recent intelligence movement, and "
            "recommended attention. Cite each bullet."
        ),
        query=f"executive summary for {mission.codename} {mission.name}",
        mission_id=mission_id,
        source_types=["mission", "operational_event", "approval", "intel_item"],
    )


def approval_summary_draft(db: Session, approval_id: int) -> SynthesisResponse:
    a = db.get(Approval, approval_id)
    if a is None:
        raise HTTPException(status_code=404, detail=f"Approval #{approval_id} not found")
    return _synthesize(
        db,
        objective=f"Approval summary draft — #{approval_id}",
        instructions=(
            "Draft an approval summary: what is being approved, who requested, "
            "the operational rationale, and the projected impact. Cite the "
            "supporting records."
        ),
        query=f"approval {a.action} entity_type={a.entity_type} entity_id={a.entity_id}",
        mission_id=a.mission_id,
        source_types=["approval", "communication", "operational_event"],
    )


def escalation_brief_draft(
    db: Session, mission_id: int, *, hours: int = 48
) -> SynthesisResponse:
    mission = db.get(Mission, mission_id)
    if mission is None or mission.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Mission #{mission_id} not found")
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return _synthesize(
        db,
        objective=f"Escalation brief draft — {mission.codename}",
        instructions=(
            "Draft a 3-5 bullet escalation brief for leadership. Lead with the "
            "most material risk, then list the supporting evidence. Conclude "
            "with the recommended escalation path. Cite every claim."
        ),
        query=f"escalation brief {mission.codename} risk pressure blockers",
        mission_id=mission_id,
        source_types=["operational_event", "approval", "execution_queue_item", "intel_item"],
        since=since,
    )


def investor_followup_draft(
    db: Session, opportunity_id: int
) -> SynthesisResponse:
    o = db.get(InvestorOpportunity, opportunity_id)
    if o is None or o.deleted_at is not None:
        raise HTTPException(
            status_code=404, detail=f"Investor opportunity #{opportunity_id} not found"
        )
    return _synthesize(
        db,
        objective=f"Investor follow-up draft — opportunity #{opportunity_id}",
        instructions=(
            "Draft a short investor follow-up message: acknowledge the prior "
            "thread, summarize the relevant operational momentum, propose the "
            "next concrete step. Tone: aerospace-grade, not promotional. "
            "Cite the supporting context."
        ),
        query=f"investor opportunity #{opportunity_id} stage {o.stage} {o.next_step or ''}",
        entity_type="investor_opportunity",
        entity_id=opportunity_id,
        source_types=["communication", "note", "operational_event"],
        limit=10,
    )


def supplier_outreach_draft(
    db: Session, supplier_id: int
) -> SynthesisResponse:
    return _synthesize(
        db,
        objective=f"Supplier outreach draft — supplier #{supplier_id}",
        instructions=(
            "Draft an outreach message to the supplier covering the operational "
            "context, current concerns, and the proposed coordination. Cite "
            "supporting context. No commitments — operator must review."
        ),
        query=f"supplier #{supplier_id} outreach status",
        entity_type="supplier",
        entity_id=supplier_id,
        source_types=["intel_item", "communication", "note"],
    )
