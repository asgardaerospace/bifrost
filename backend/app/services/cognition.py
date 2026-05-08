"""Cognition pipeline — command interpretation grounded in retrieval.

Doctrine: AI is not freeform. The pipeline accepts a natural-language command,
classifies its intent against a curated set, runs a deterministic retrieval
plan, expands the context with mission/graph state, then synthesizes a
grounded response with citations.

Pipeline stages:

    command (natural language)
       ↓ classify_intent           — keyword/regex + canonical intents
       ↓ build_retrieval_plan      — source_types + scope + temporal window
       ↓ retrieval.search()        — semantic + keyword + recency
       ↓ context_expand            — pull mission pressure + queue + impacts
       ↓ assemble_prompt           — [#k] markers + system prompt + task
       ↓ llm.synthesize            — local-deterministic-v1 default
       ↓ extract_citations         — only chunks the LLM cited
       ↓ CognitionResponse

Weak retrieval refuses gracefully (INSUFFICIENT CONTEXT, confidence=0). The
pipeline never fabricates operational state. No autonomous actions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intel import IntelItem
from app.models.mission import Mission
from app.services import retrieval as retrieval_service
from app.services.llm import get_provider as get_llm_provider
from app.services.rag import (
    SYSTEM_PROMPT,
    Citation,
    SynthesisResponse,
    _build_prompt,
    _filter_used_citations,
    _format_retrieval_block,
)


# ---------------------------------------------------------------------------
# intent table — curated, finite
# ---------------------------------------------------------------------------


@dataclass
class Intent:
    intent_id: str
    label: str
    keywords: tuple[str, ...]
    source_types: tuple[str, ...]
    instructions: str
    temporal_hours: Optional[int] = None  # if set, filter retrieval since now-N
    requires_mission: bool = False  # set true when intent reads as mission-scoped


INTENTS: tuple[Intent, ...] = (
    Intent(
        intent_id="missions_under_pressure",
        label="Show missions under rising pressure",
        keywords=("rising pressure", "pressure increasing", "missions under pressure", "high pressure"),
        source_types=("mission", "operational_event", "approval", "intel_item"),
        instructions=(
            "List the missions whose pressure is rising and why. Cite the events / "
            "approvals / intel impacts that are driving each mission's score."
        ),
    ),
    Intent(
        intent_id="supplier_instability",
        label="Summarize supplier instability",
        keywords=("supplier instability", "supplier risk", "supplier", "vendor risk"),
        source_types=("intel_item", "operational_event"),
        instructions=(
            "Summarize current supplier instability. Cluster by supplier, name "
            "the affected missions, and cite intel signals that flagged the risk."
        ),
    ),
    Intent(
        intent_id="explain_pressure",
        label="Explain why mission pressure increased",
        keywords=("explain", "why", "pressure increased", "pressure rose", "pressure"),
        source_types=("operational_event", "approval", "execution_queue_item", "intel_item"),
        instructions=(
            "Explain the dominant drivers of the mission's pressure, citing the "
            "specific events, approvals, queue items, or intel signals that "
            "contributed."
        ),
        requires_mission=True,
    ),
    Intent(
        intent_id="manufacturing_blockers",
        label="Show unresolved blockers affecting manufacturing",
        keywords=("manufacturing", "blockers", "unresolved blockers", "manufacturing blockers"),
        source_types=("execution_queue_item", "approval", "operational_event"),
        instructions=(
            "List unresolved blockers in manufacturing. For each, cite the queue "
            "item or approval row and the affected mission."
        ),
    ),
    Intent(
        intent_id="funding_movement",
        label="Summarize aerospace funding movement",
        keywords=("funding movement", "aerospace funding", "vc funding", "investor movement", "funding"),
        source_types=("intel_item",),
        temporal_hours=72,
        instructions=(
            "Summarize aerospace funding movement in the recent window. Cluster "
            "by investor or fund. Cite each signal."
        ),
    ),
    Intent(
        intent_id="weekly_change",
        label="What changed operationally this week",
        keywords=("this week", "what changed", "weekly", "weekly change"),
        source_types=("operational_event", "mission", "approval", "intel_item"),
        temporal_hours=168,
        instructions=(
            "Summarize material operational change in the last 7 days. Group by "
            "domain (mission state, approvals, intelligence). Cite every claim."
        ),
    ),
    Intent(
        intent_id="executive_priorities",
        label="Show executive priorities",
        keywords=("executive priorities", "executive attention", "leadership", "top priorities"),
        source_types=("mission", "intel_item", "approval"),
        instructions=(
            "Identify the top operational priorities for executives. Reference "
            "missions under pressure and intelligence requiring attention."
        ),
    ),
    Intent(
        intent_id="procurement_propulsion",
        label="Identify procurement opportunities affecting propulsion",
        keywords=("procurement", "propulsion", "rfp", "rfi", "contract"),
        source_types=("intel_item",),
        instructions=(
            "List procurement opportunities relevant to propulsion. Cite each "
            "intel signal and note the mission it most affects."
        ),
    ),
    Intent(
        intent_id="investor_movement",
        label="Summarize investor movement impacting current missions",
        keywords=("investor movement", "capital movement", "investor", "fund"),
        source_types=("intel_item", "operational_event"),
        temporal_hours=336,
        instructions=(
            "Summarize investor movement impacting current missions. Cite each "
            "signal."
        ),
    ),
)


# ---------------------------------------------------------------------------
# intent classification
# ---------------------------------------------------------------------------


@dataclass
class IntentClassification:
    intent: Intent
    matched_keywords: list[str]
    confidence: float


def classify_intent(command: str) -> Optional[IntentClassification]:
    text = (command or "").lower()
    best: Optional[IntentClassification] = None
    for intent in INTENTS:
        hits = [kw for kw in intent.keywords if kw in text]
        if not hits:
            continue
        # Confidence scales with hit count + keyword specificity (longest hit).
        conf = min(0.95, 0.4 + 0.15 * len(hits) + 0.05 * (max(len(h.split()) for h in hits) - 1))
        if best is None or conf > best.confidence:
            best = IntentClassification(
                intent=intent, matched_keywords=hits, confidence=conf
            )
    return best


# ---------------------------------------------------------------------------
# command response
# ---------------------------------------------------------------------------


@dataclass
class CognitionResponse:
    command: str
    intent_id: Optional[str]
    intent_label: Optional[str]
    matched_keywords: list[str]
    intent_confidence: float
    synthesis: SynthesisResponse  # carries summary + citations + retrieval trace + confidence


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------


_MISSION_REF_RE = re.compile(r"\b([A-Z]{2,}[A-Z0-9-]{1,32})\b")


def _resolve_mission_id(db: Session, command: str) -> Optional[int]:
    """Best-effort resolver: look for a known mission codename in the command
    text. Falls back to None if no codename matches."""
    matches = _MISSION_REF_RE.findall(command)
    for token in matches:
        m = db.scalars(select(Mission).where(Mission.codename == token)).first()
        if m is not None and m.deleted_at is None:
            return m.id
    return None


def _weak_response(command: str, classification: Optional[IntentClassification], reason: str) -> CognitionResponse:
    return CognitionResponse(
        command=command,
        intent_id=classification.intent.intent_id if classification else None,
        intent_label=classification.intent.label if classification else None,
        matched_keywords=classification.matched_keywords if classification else [],
        intent_confidence=classification.confidence if classification else 0.0,
        synthesis=SynthesisResponse(
            objective=classification.intent.label if classification else "Cognition",
            summary=reason,
            confidence=0.0,
            weak_retrieval=True,
            citations=[],
            retrieval_trace=retrieval_service.RetrievalTrace(
                query=command,
                candidates_considered=0,
                chunks_returned=0,
                scoped_mission_id=None,
                scoped_entity_type=None,
                scoped_entity_id=None,
                since=None,
                embedding_model=get_llm_provider().name,
                weights={},
            ),
            model=get_llm_provider().name,
        ),
    )


def execute(db: Session, command: str, *, mission_id: Optional[int] = None) -> CognitionResponse:
    classification = classify_intent(command)
    if classification is None:
        return _weak_response(
            command,
            None,
            "INSUFFICIENT INTENT — command did not match any curated cognition intent. "
            "Try a more specific command (e.g. 'show missions under rising pressure').",
        )
    intent = classification.intent

    # Mission scope resolution (if intent requires it).
    if intent.requires_mission and mission_id is None:
        mission_id = _resolve_mission_id(db, command)
        if mission_id is None:
            return _weak_response(
                command,
                classification,
                "INSUFFICIENT SCOPE — this intent requires a mission codename "
                "(e.g. 'explain why ORION pressure increased'). No codename was "
                "recognized in the command.",
            )

    since = None
    if intent.temporal_hours is not None:
        since = datetime.now(timezone.utc) - timedelta(hours=intent.temporal_hours)

    results, trace = retrieval_service.search(
        db,
        query=command,
        mission_id=mission_id if intent.requires_mission else None,
        source_types=list(intent.source_types),
        since=since,
        limit=10,
    )

    if retrieval_service.is_weak(results):
        return CognitionResponse(
            command=command,
            intent_id=intent.intent_id,
            intent_label=intent.label,
            matched_keywords=classification.matched_keywords,
            intent_confidence=classification.confidence,
            synthesis=SynthesisResponse(
                objective=intent.label,
                summary=(
                    "INSUFFICIENT CONTEXT — retrieval did not return chunks above "
                    "the relevance threshold. No synthesis produced. Tighten "
                    "scope, ingest more intelligence, or rephrase the query."
                ),
                confidence=0.0,
                weak_retrieval=True,
                citations=[],
                retrieval_trace=trace,
                model=get_llm_provider().name,
            ),
        )

    block, citations = _format_retrieval_block(results)
    user_prompt = _build_prompt(
        task=intent.label, instructions=intent.instructions, retrieval_block=block
    )
    provider = get_llm_provider()
    llm_resp = provider.synthesize(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    used_citations = _filter_used_citations(llm_resp.text, citations)

    synth = SynthesisResponse(
        objective=intent.label,
        summary=llm_resp.text,
        confidence=llm_resp.confidence * classification.confidence,
        weak_retrieval=False,
        citations=used_citations or citations,
        retrieval_trace=trace,
        model=llm_resp.model,
    )

    return CognitionResponse(
        command=command,
        intent_id=intent.intent_id,
        intent_label=intent.label,
        matched_keywords=classification.matched_keywords,
        intent_confidence=classification.confidence,
        synthesis=synth,
    )
