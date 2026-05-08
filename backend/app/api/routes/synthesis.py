"""RAG synthesis routes — retrieval-grounded mission summaries.

Doctrine: AI may summarize, recommend, draft. AI may NOT mutate state. These
routes are read-only and always cite their sources.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.memory import (
    CitationRead,
    RelatedMissionRead,
    RelatedMissionsResponse,
    RetrievalScoreComponents,
    RetrievalTraceRead,
    SynthesisResponseRead,
)
from app.services import rag as rag_service

router = APIRouter()


def _to_read(resp) -> SynthesisResponseRead:
    return SynthesisResponseRead(
        objective=resp.objective,
        summary=resp.summary,
        confidence=resp.confidence,
        weak_retrieval=resp.weak_retrieval,
        citations=[
            CitationRead(
                marker=c.marker,
                chunk_id=c.chunk_id,
                record_id=c.record_id,
                source_type=c.source_type,
                source_id=c.source_id,
                title=c.title,
                excerpt=c.excerpt,
            )
            for c in resp.citations
        ],
        retrieval_trace=RetrievalTraceRead(
            query=resp.retrieval_trace.query,
            candidates_considered=resp.retrieval_trace.candidates_considered,
            chunks_returned=resp.retrieval_trace.chunks_returned,
            scoped_mission_id=resp.retrieval_trace.scoped_mission_id,
            scoped_entity_type=resp.retrieval_trace.scoped_entity_type,
            scoped_entity_id=resp.retrieval_trace.scoped_entity_id,
            since=resp.retrieval_trace.since,
            embedding_model=resp.retrieval_trace.embedding_model,
            weights=resp.retrieval_trace.weights,
        ),
        model=resp.model,
    )


@router.post(
    "/missions/{mission_id}/synthesize",
    response_model=SynthesisResponseRead,
)
def synthesize_mission(
    mission_id: int, db: Session = Depends(get_db)
) -> SynthesisResponseRead:
    return _to_read(rag_service.summarize_mission(db, mission_id))


@router.post(
    "/missions/{mission_id}/synthesize/pressure",
    response_model=SynthesisResponseRead,
)
def synthesize_pressure(
    mission_id: int, db: Session = Depends(get_db)
) -> SynthesisResponseRead:
    return _to_read(rag_service.explain_pressure(db, mission_id))


@router.post(
    "/missions/{mission_id}/synthesize/history",
    response_model=SynthesisResponseRead,
)
def synthesize_history(
    mission_id: int,
    days: int = Query(14, ge=1, le=365),
    db: Session = Depends(get_db),
) -> SynthesisResponseRead:
    return _to_read(rag_service.synthesize_history(db, mission_id, days=days))


@router.get(
    "/missions/{mission_id}/related",
    response_model=RelatedMissionsResponse,
)
def related_missions(
    mission_id: int,
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
) -> RelatedMissionsResponse:
    related, trace = rag_service.find_related_missions(db, mission_id, limit=limit)
    return RelatedMissionsResponse(
        related=[
            RelatedMissionRead(
                mission_id=r["mission_id"],
                title=r.get("title"),
                score=r["score"],
                components=RetrievalScoreComponents(**r["components"]),
                excerpt=r["excerpt"],
            )
            for r in related
        ],
        trace=RetrievalTraceRead(
            query=trace.query,
            candidates_considered=trace.candidates_considered,
            chunks_returned=trace.chunks_returned,
            scoped_mission_id=trace.scoped_mission_id,
            scoped_entity_type=trace.scoped_entity_type,
            scoped_entity_id=trace.scoped_entity_id,
            since=trace.since,
            embedding_model=trace.embedding_model,
            weights=trace.weights,
        ),
    )
