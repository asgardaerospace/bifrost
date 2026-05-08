"""Memory service — source-driven memory record + chunk lifecycle.

Doctrine: a memory record represents one operational artifact; its semantic
chunks are fully derived. When a source changes (detected via source_hash),
old chunks are dropped and replaced. Embedding is synchronous in Sprint 3
(no distributed queue) and runs in the same DB transaction as ingestion so
retrieval is consistent immediately.

Source kinds supported:
    mission, operational_event, approval, communication, intel_item, note,
    queue_item, document. The `ingest_*` helpers normalize each into a
    MemoryRecord row.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.memory import EMBEDDING_DIM, MemoryRecord, SemanticChunk
from app.services.chunking import Chunk, chunk_text
from app.services.embeddings import get_provider as get_embed_provider


# ---------------------------------------------------------------------------
# hashing + content assembly
# ---------------------------------------------------------------------------


def _hash_source(source_type: str, source_id: int, content: str) -> str:
    h = hashlib.sha256()
    h.update(source_type.encode("utf-8"))
    h.update(b"\x00")
    h.update(str(source_id).encode("utf-8"))
    h.update(b"\x00")
    h.update((content or "").encode("utf-8"))
    return h.hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# core upsert
# ---------------------------------------------------------------------------


def upsert_record(
    db: Session,
    *,
    source_type: str,
    source_id: int,
    content: str,
    title: Optional[str] = None,
    mission_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    created_by: Optional[str] = None,
    source_occurred_at: Optional[datetime] = None,
    meta: Optional[dict[str, Any]] = None,
    embed_now: bool = True,
) -> MemoryRecord:
    """Idempotent upsert keyed on (source_type, source_id).

    Returns the record. If `embed_now`, regenerates chunks + embeddings
    inline (only when source_hash actually changed). Caller is responsible
    for committing.
    """
    new_hash = _hash_source(source_type, source_id, content)
    existing = db.scalars(
        select(MemoryRecord).where(
            MemoryRecord.source_type == source_type,
            MemoryRecord.source_id == source_id,
        )
    ).first()

    if existing is None:
        record = MemoryRecord(
            source_type=source_type,
            source_id=source_id,
            source_hash=new_hash,
            title=title,
            content=content,
            mission_id=mission_id,
            entity_type=entity_type,
            entity_id=entity_id,
            created_by=created_by,
            source_occurred_at=source_occurred_at or _now(),
            version=1,
            embedding_status="pending",
            token_count=len((content or "").split()),
            meta=meta,
        )
        db.add(record)
        db.flush()
        if embed_now:
            refresh_chunks(db, record)
        return record

    # Record exists — only refresh if hash changed (idempotent).
    changed = existing.source_hash != new_hash
    if title is not None:
        existing.title = title
    if mission_id is not None:
        existing.mission_id = mission_id
    if entity_type is not None:
        existing.entity_type = entity_type
    if entity_id is not None:
        existing.entity_id = entity_id
    if source_occurred_at is not None:
        existing.source_occurred_at = source_occurred_at
    if meta is not None:
        existing.meta = meta
    if changed:
        existing.content = content
        existing.source_hash = new_hash
        existing.version += 1
        existing.token_count = len((content or "").split())
        existing.embedding_status = "pending"
        existing.embedded_at = None
        if embed_now:
            refresh_chunks(db, existing)
    return existing


def refresh_chunks(db: Session, record: MemoryRecord) -> int:
    """Regenerate chunks + embeddings for a record. Returns chunk count.

    Only the chunks belonging to this record are replaced — never another
    record's. Embedding errors are caught and the record is marked failed
    so the operator can retry without losing the rest of the pipeline.
    """
    db.execute(
        delete(SemanticChunk).where(SemanticChunk.memory_record_id == record.id)
    )
    db.flush()

    chunks: List[Chunk] = chunk_text(
        f"{record.title}\n\n{record.content}" if record.title else record.content
    )
    if not chunks:
        record.embedding_status = "skipped"
        record.embedded_at = _now()
        return 0

    provider = get_embed_provider()
    try:
        embeddings = provider.embed([c.text for c in chunks])
    except Exception:
        record.embedding_status = "failed"
        record.embedded_at = _now()
        return 0

    for chunk, vec in zip(chunks, embeddings):
        db.add(
            SemanticChunk(
                memory_record_id=record.id,
                chunk_index=chunk.index,
                text=chunk.text,
                token_count=chunk.token_count,
                embedding=vec,
                embedding_model=provider.name,
                embedding_dim=provider.dim,
                source_hash=record.source_hash,
            )
        )
    record.embedding_status = "ready"
    record.embedded_at = _now()
    db.flush()
    return len(chunks)


def soft_delete_for_source(
    db: Session, *, source_type: str, source_id: int
) -> None:
    record = db.scalars(
        select(MemoryRecord).where(
            MemoryRecord.source_type == source_type,
            MemoryRecord.source_id == source_id,
        )
    ).first()
    if record is None:
        return
    record.deleted_at = _now()
    db.flush()


# ---------------------------------------------------------------------------
# convenience ingestion helpers per canonical source type
# ---------------------------------------------------------------------------


def ingest_mission(db: Session, mission) -> MemoryRecord:
    """Project a Mission into memory. Called on create + update triggers."""
    parts = [
        f"Codename: {mission.codename}",
        f"Name: {mission.name}",
        f"Status: {mission.status} · Priority: {mission.priority} · Health: {mission.health_status}",
    ]
    if mission.description:
        parts.append("")
        parts.append(mission.description)
    return upsert_record(
        db,
        source_type="mission",
        source_id=mission.id,
        content="\n".join(parts),
        title=f"Mission {mission.codename} — {mission.name}",
        mission_id=mission.id,
        entity_type="mission",
        entity_id=mission.id,
        source_occurred_at=mission.updated_at or mission.created_at,
        meta={
            "status": mission.status,
            "priority": mission.priority,
            "health": mission.health_status,
        },
    )


def ingest_operational_event(db: Session, event) -> MemoryRecord:
    payload_text = ""
    if isinstance(event.payload, dict):
        payload_text = " ".join(f"{k}={v}" for k, v in event.payload.items() if v is not None)
    parts = [
        f"Event: {event.event_type} (topic={event.topic}, severity={event.severity})",
    ]
    if event.actor:
        parts.append(f"Actor: {event.actor}")
    if payload_text:
        parts.append(payload_text)
    return upsert_record(
        db,
        source_type="operational_event",
        source_id=event.id,
        content="\n".join(parts),
        title=event.event_type,
        mission_id=event.mission_id,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        created_by=event.actor,
        source_occurred_at=event.created_at,
        meta={"topic": event.topic, "severity": event.severity},
    )


def ingest_approval(db: Session, approval) -> MemoryRecord:
    parts = [
        f"Approval action: {approval.action}",
        f"Status: {approval.status}",
    ]
    if approval.requested_by:
        parts.append(f"Requested by: {approval.requested_by}")
    if approval.reviewer:
        parts.append(f"Reviewer: {approval.reviewer}")
    if approval.decision_note:
        parts.append("")
        parts.append(approval.decision_note)
    return upsert_record(
        db,
        source_type="approval",
        source_id=approval.id,
        content="\n".join(parts),
        title=f"Approval: {approval.action}",
        mission_id=approval.mission_id,
        entity_type=approval.entity_type,
        entity_id=approval.entity_id,
        created_by=approval.reviewer or approval.requested_by,
        source_occurred_at=approval.reviewed_at or approval.created_at,
        meta={"action": approval.action, "status": approval.status},
    )


def ingest_queue_item(db: Session, item) -> MemoryRecord:
    parts = [
        f"Queue item: {item.title}",
        f"Type: {item.item_type} · Status: {item.status} · Priority: {item.priority_score}",
    ]
    if item.summary:
        parts.append("")
        parts.append(item.summary)
    return upsert_record(
        db,
        source_type="execution_queue_item",
        source_id=item.id,
        content="\n".join(parts),
        title=item.title,
        mission_id=item.mission_id,
        entity_type="execution_queue_item",
        entity_id=item.id,
        created_by=item.owner,
        source_occurred_at=item.updated_at,
        meta={
            "item_type": item.item_type,
            "status": item.status,
            "requires_approval": item.requires_approval,
        },
    )


def ingest_communication(db: Session, comm) -> MemoryRecord:
    parts = [
        f"{comm.channel} {comm.direction} — {comm.status}",
    ]
    if comm.subject:
        parts.append(f"Subject: {comm.subject}")
    if comm.body:
        parts.append("")
        parts.append(comm.body)
    return upsert_record(
        db,
        source_type="communication",
        source_id=comm.id,
        content="\n".join(parts),
        title=comm.subject or f"{comm.channel} {comm.direction}",
        mission_id=comm.mission_id,
        entity_type=comm.entity_type,
        entity_id=comm.entity_id,
        source_occurred_at=comm.sent_at or comm.created_at,
        meta={
            "channel": comm.channel,
            "direction": comm.direction,
            "status": comm.status,
        },
    )


def ingest_intel_item(db: Session, intel) -> MemoryRecord:
    parts = [
        f"{intel.title}",
        f"Source: {intel.source}",
    ]
    if intel.region:
        parts.append(f"Region: {intel.region}")
    if intel.summary:
        parts.append("")
        parts.append(intel.summary)
    return upsert_record(
        db,
        source_type="intel_item",
        source_id=intel.id,
        content="\n".join(parts),
        title=intel.title,
        mission_id=intel.mission_id,
        entity_type="intel_item",
        entity_id=intel.id,
        source_occurred_at=intel.published_at or intel.created_at,
        meta={
            "source": intel.source,
            "category": intel.category,
            "strategic_relevance_score": intel.strategic_relevance_score,
        },
    )


def ingest_note(db: Session, note) -> MemoryRecord:
    return upsert_record(
        db,
        source_type="note",
        source_id=note.id,
        content=note.body or "",
        title=f"Note on {note.entity_type}#{note.entity_id}",
        entity_type=note.entity_type,
        entity_id=note.entity_id,
        created_by=note.author,
        source_occurred_at=note.created_at,
    )


# ---------------------------------------------------------------------------
# read helpers
# ---------------------------------------------------------------------------


def get_record(db: Session, record_id: int) -> Optional[MemoryRecord]:
    rec = db.get(MemoryRecord, record_id)
    if rec is None or rec.deleted_at is not None:
        return None
    return rec


def list_for_mission(
    db: Session, mission_id: int, *, limit: int = 200
) -> List[MemoryRecord]:
    stmt = (
        select(MemoryRecord)
        .where(MemoryRecord.mission_id == mission_id)
        .where(MemoryRecord.deleted_at.is_(None))
        .order_by(MemoryRecord.source_occurred_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def list_for_entity(
    db: Session, entity_type: str, entity_id: int, *, limit: int = 200
) -> List[MemoryRecord]:
    stmt = (
        select(MemoryRecord)
        .where(MemoryRecord.entity_type == entity_type)
        .where(MemoryRecord.entity_id == entity_id)
        .where(MemoryRecord.deleted_at.is_(None))
        .order_by(MemoryRecord.source_occurred_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
