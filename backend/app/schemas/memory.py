"""Memory + retrieval + synthesis schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from app.schemas.base import ORMModel, TimestampedRead


# --- memory ---------------------------------------------------------------


class MemoryRecordRead(TimestampedRead):
    source_type: str
    source_id: int
    source_hash: str
    title: Optional[str] = None
    content: str
    mission_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    created_by: Optional[str] = None
    source_occurred_at: Optional[datetime] = None
    version: int
    embedding_status: str
    embedded_at: Optional[datetime] = None
    token_count: int
    meta: Optional[dict[str, Any]] = None


class MemoryRecordCreate(ORMModel):
    source_type: str
    source_id: int
    content: str
    title: Optional[str] = None
    mission_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    created_by: Optional[str] = None
    source_occurred_at: Optional[datetime] = None
    meta: Optional[dict[str, Any]] = None


class SemanticChunkRead(ORMModel):
    id: int
    memory_record_id: int
    chunk_index: int
    text: str
    token_count: int
    embedding_model: Optional[str] = None
    embedding_dim: Optional[int] = None
    source_hash: str
    created_at: datetime


# --- retrieval ------------------------------------------------------------


class RetrievalScoreComponents(ORMModel):
    semantic: float
    keyword: float
    recency: float
    w_semantic: float
    w_keyword: float
    w_recency: float


class RetrievalResultRead(ORMModel):
    chunk_id: int
    record_id: int
    source_type: str
    source_id: int
    title: Optional[str] = None
    text: str
    score: float
    components: RetrievalScoreComponents
    mission_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    occurred_at: Optional[datetime] = None
    chunk_index: int
    embedding_model: Optional[str] = None


class RetrievalTraceRead(ORMModel):
    query: str
    candidates_considered: int
    chunks_returned: int
    scoped_mission_id: Optional[int] = None
    scoped_entity_type: Optional[str] = None
    scoped_entity_id: Optional[int] = None
    since: Optional[datetime] = None
    embedding_model: str
    weights: dict[str, float]


class SearchQuery(ORMModel):
    query: str
    mission_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    since: Optional[datetime] = None
    source_types: Optional[List[str]] = None
    limit: int = 10


class SearchResponse(ORMModel):
    results: List[RetrievalResultRead]
    trace: RetrievalTraceRead


# --- synthesis (RAG output) -----------------------------------------------


class CitationRead(ORMModel):
    marker: str
    chunk_id: int
    record_id: int
    source_type: str
    source_id: int
    title: Optional[str] = None
    excerpt: str


class SynthesisResponseRead(ORMModel):
    objective: str
    summary: str
    confidence: float
    weak_retrieval: bool
    citations: List[CitationRead]
    retrieval_trace: RetrievalTraceRead
    model: str


class RelatedMissionRead(ORMModel):
    mission_id: int
    title: Optional[str] = None
    score: float
    components: RetrievalScoreComponents
    excerpt: str


class RelatedMissionsResponse(ORMModel):
    related: List[RelatedMissionRead]
    trace: RetrievalTraceRead
