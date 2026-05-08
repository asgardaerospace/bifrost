"""Executive intelligence synthesis routes (Sprint 4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.memory import (
    CitationRead,
    RetrievalTraceRead,
    SynthesisResponseRead,
)
from app.services import executive_brief as exec_brief_service

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


@router.get(
    "/executive/intelligence/brief",
    response_model=SynthesisResponseRead,
)
def daily_brief(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> SynthesisResponseRead:
    return _to_read(exec_brief_service.daily_brief(db, hours=hours))


@router.get(
    "/missions/{mission_id}/intelligence/synthesize",
    response_model=SynthesisResponseRead,
)
def mission_intel_synthesis(
    mission_id: int,
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> SynthesisResponseRead:
    return _to_read(
        exec_brief_service.mission_impact_summary(db, mission_id, hours=hours)
    )
