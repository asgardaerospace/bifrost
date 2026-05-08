"""Retrieval engine — hybrid semantic + keyword + recency.

Sprint 3 architecture:
  1. Filter chunks by mission/entity/temporal scope at the SQL layer.
  2. Pull candidate chunks into Python.
  3. Score each candidate with three deterministic components:
       - semantic similarity (cosine, weight=W_SEMANTIC)
       - keyword overlap (Jaccard on lowercased word sets, weight=W_KEYWORD)
       - recency decay (half-life HALF_LIFE_DAYS, weight=W_RECENCY)
  4. Sort, return top-k with full attribution + score breakdown.

Why Python-side: dataset is small in Sprint 3 (~thousands of chunks). Once
the in-DB <=> operator is needed, the pipeline can be ported to Postgres
without changing the result shape — the score components are explicit.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.memory import MemoryRecord, SemanticChunk
from app.services.embeddings import get_provider as get_embed_provider


# Scoring weights (tunable; sum > 1 fine — final scores are unbounded but
# normalized for display in `RetrievalResult.score`).
W_SEMANTIC = 0.65
W_KEYWORD = 0.20
W_RECENCY = 0.15
HALF_LIFE_DAYS = 14.0


_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall((text or "").lower()))


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _recency_decay(occurred_at: Optional[datetime], now: datetime) -> float:
    if occurred_at is None:
        return 0.5
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - occurred_at).total_seconds() / 86400.0)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


@dataclass
class RetrievalResult:
    chunk_id: int
    record_id: int
    source_type: str
    source_id: int
    title: Optional[str]
    text: str
    score: float
    components: dict[str, float]
    mission_id: Optional[int]
    entity_type: Optional[str]
    entity_id: Optional[int]
    occurred_at: Optional[datetime]
    chunk_index: int
    embedding_model: Optional[str]


@dataclass
class RetrievalTrace:
    query: str
    candidates_considered: int
    chunks_returned: int
    scoped_mission_id: Optional[int]
    scoped_entity_type: Optional[str]
    scoped_entity_id: Optional[int]
    since: Optional[datetime]
    embedding_model: str
    weights: dict[str, float]


def search(
    db: Session,
    *,
    query: str,
    mission_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    since: Optional[datetime] = None,
    source_types: Optional[List[str]] = None,
    limit: int = 10,
    candidate_limit: int = 500,
) -> tuple[List[RetrievalResult], RetrievalTrace]:
    """Hybrid retrieval. Returns (results, trace) for explainability."""
    provider = get_embed_provider()
    qvec = provider.embed_one(query) if query else None
    qtokens = _tokens(query)
    now = datetime.now(timezone.utc)

    stmt = (
        select(SemanticChunk)
        .join(SemanticChunk.record)
        .where(MemoryRecord.deleted_at.is_(None))
        .options(selectinload(SemanticChunk.record))
    )
    if mission_id is not None:
        stmt = stmt.where(MemoryRecord.mission_id == mission_id)
    if entity_type is not None:
        stmt = stmt.where(MemoryRecord.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(MemoryRecord.entity_id == entity_id)
    if since is not None:
        stmt = stmt.where(MemoryRecord.source_occurred_at >= since)
    if source_types:
        stmt = stmt.where(MemoryRecord.source_type.in_(source_types))
    stmt = stmt.limit(candidate_limit)

    chunks: List[SemanticChunk] = list(db.scalars(stmt).all())

    scored: List[RetrievalResult] = []
    for chunk in chunks:
        record = chunk.record
        sem = (
            _cosine(qvec, chunk.embedding)
            if qvec is not None and chunk.embedding
            else 0.0
        )
        kw = _jaccard(qtokens, _tokens(chunk.text))
        rec = _recency_decay(record.source_occurred_at, now)
        score = W_SEMANTIC * sem + W_KEYWORD * kw + W_RECENCY * rec
        scored.append(
            RetrievalResult(
                chunk_id=chunk.id,
                record_id=record.id,
                source_type=record.source_type,
                source_id=record.source_id,
                title=record.title,
                text=chunk.text,
                score=score,
                components={
                    "semantic": sem,
                    "keyword": kw,
                    "recency": rec,
                    "w_semantic": W_SEMANTIC,
                    "w_keyword": W_KEYWORD,
                    "w_recency": W_RECENCY,
                },
                mission_id=record.mission_id,
                entity_type=record.entity_type,
                entity_id=record.entity_id,
                occurred_at=record.source_occurred_at,
                chunk_index=chunk.chunk_index,
                embedding_model=chunk.embedding_model,
            )
        )

    scored.sort(key=lambda r: -r.score)
    top = scored[:limit]
    trace = RetrievalTrace(
        query=query,
        candidates_considered=len(chunks),
        chunks_returned=len(top),
        scoped_mission_id=mission_id,
        scoped_entity_type=entity_type,
        scoped_entity_id=entity_id,
        since=since,
        embedding_model=provider.name,
        weights={
            "semantic": W_SEMANTIC,
            "keyword": W_KEYWORD,
            "recency": W_RECENCY,
        },
    )
    return top, trace


def is_weak(results: List[RetrievalResult], *, threshold: float = 0.15) -> bool:
    """Return True when the top result's score is below the confidence floor.

    Used by the RAG layer to decide whether to surface a synthesized answer
    or report `weak_retrieval` and decline to fabricate.
    """
    if not results:
        return True
    return results[0].score < threshold
