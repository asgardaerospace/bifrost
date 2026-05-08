"""Memory + retrieval HTTP routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.memory import (
    MemoryRecordCreate,
    MemoryRecordRead,
    SearchQuery,
    SearchResponse,
    RetrievalResultRead,
    RetrievalScoreComponents,
    RetrievalTraceRead,
)
from app.services import memory as memory_service
from app.services import retrieval as retrieval_service

router = APIRouter()


def _result_to_read(r) -> RetrievalResultRead:
    return RetrievalResultRead(
        chunk_id=r.chunk_id,
        record_id=r.record_id,
        source_type=r.source_type,
        source_id=r.source_id,
        title=r.title,
        text=r.text,
        score=r.score,
        components=RetrievalScoreComponents(**r.components),
        mission_id=r.mission_id,
        entity_type=r.entity_type,
        entity_id=r.entity_id,
        occurred_at=r.occurred_at,
        chunk_index=r.chunk_index,
        embedding_model=r.embedding_model,
    )


def _trace_to_read(t) -> RetrievalTraceRead:
    return RetrievalTraceRead(
        query=t.query,
        candidates_considered=t.candidates_considered,
        chunks_returned=t.chunks_returned,
        scoped_mission_id=t.scoped_mission_id,
        scoped_entity_type=t.scoped_entity_type,
        scoped_entity_id=t.scoped_entity_id,
        since=t.since,
        embedding_model=t.embedding_model,
        weights=t.weights,
    )


@router.post("/memory/search", response_model=SearchResponse)
def search_memory(
    payload: SearchQuery, db: Session = Depends(get_db)
) -> SearchResponse:
    results, trace = retrieval_service.search(
        db,
        query=payload.query,
        mission_id=payload.mission_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        since=payload.since,
        source_types=payload.source_types,
        limit=payload.limit,
    )
    return SearchResponse(
        results=[_result_to_read(r) for r in results],
        trace=_trace_to_read(trace),
    )


@router.get(
    "/memory/mission/{mission_id}", response_model=list[MemoryRecordRead]
)
def memory_for_mission(
    mission_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[MemoryRecordRead]:
    rows = memory_service.list_for_mission(db, mission_id, limit=limit)
    return [MemoryRecordRead.model_validate(r) for r in rows]


@router.get(
    "/memory/entity/{entity_type}/{entity_id}",
    response_model=list[MemoryRecordRead],
)
def memory_for_entity(
    entity_type: str,
    entity_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[MemoryRecordRead]:
    rows = memory_service.list_for_entity(db, entity_type, entity_id, limit=limit)
    return [MemoryRecordRead.model_validate(r) for r in rows]


@router.post(
    "/memory/records",
    response_model=MemoryRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def create_memory_record(
    payload: MemoryRecordCreate, db: Session = Depends(get_db)
) -> MemoryRecordRead:
    """Manual ingestion. Idempotent on (source_type, source_id) — re-posting
    the same source updates content + refreshes embeddings if hash changed."""
    record = memory_service.upsert_record(
        db,
        source_type=payload.source_type,
        source_id=payload.source_id,
        content=payload.content,
        title=payload.title,
        mission_id=payload.mission_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        created_by=payload.created_by,
        source_occurred_at=payload.source_occurred_at,
        meta=payload.meta,
        embed_now=True,
    )
    db.commit()
    db.refresh(record)
    return MemoryRecordRead.model_validate(record)


@router.post(
    "/memory/records/{record_id}/refresh",
    response_model=MemoryRecordRead,
)
def refresh_record(record_id: int, db: Session = Depends(get_db)) -> MemoryRecordRead:
    record = memory_service.get_record(db, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Memory record #{record_id} not found")
    memory_service.refresh_chunks(db, record)
    db.commit()
    db.refresh(record)
    return MemoryRecordRead.model_validate(record)
