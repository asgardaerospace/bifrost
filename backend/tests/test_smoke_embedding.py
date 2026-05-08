"""Sprint 3 — embedding provider determinism + memory service idempotency."""

from __future__ import annotations

from app.models.memory import MemoryRecord, SemanticChunk
from app.services import memory as memory_service
from app.services.embeddings import get_provider
from app.services.embeddings.local import LocalHashEmbeddingProvider


def test_local_provider_deterministic():
    p = LocalHashEmbeddingProvider()
    a = p.embed_one("Mission Starline-1 propulsion qualification")
    b = p.embed_one("Mission Starline-1 propulsion qualification")
    assert a == b
    assert len(a) == p.dim


def test_local_provider_token_overlap_yields_higher_similarity():
    p = LocalHashEmbeddingProvider()
    a = p.embed_one("propulsion qualification static fire")
    near = p.embed_one("static fire propulsion test")
    far = p.embed_one("market campaign sector accounts")

    def cos(x, y):
        return sum(i * j for i, j in zip(x, y))

    assert cos(a, near) > cos(a, far)


def test_upsert_record_creates_chunks(client, db_session):
    rec = memory_service.upsert_record(
        db_session,
        source_type="note",
        source_id=1,
        content="Mission Starline-1 has critical propulsion blockers requiring approval.",
        title="Test note",
    )
    db_session.commit()
    db_session.refresh(rec)

    assert rec.embedding_status == "ready"
    assert rec.embedded_at is not None
    chunks = (
        db_session.query(SemanticChunk)
        .filter_by(memory_record_id=rec.id)
        .all()
    )
    assert len(chunks) >= 1
    assert chunks[0].embedding is not None
    assert chunks[0].embedding_dim == get_provider().dim


def test_upsert_idempotent_on_unchanged_content(db_session):
    a = memory_service.upsert_record(
        db_session,
        source_type="note",
        source_id=2,
        content="Same content",
    )
    db_session.commit()
    a_id = a.id
    a_hash = a.source_hash
    a_version = a.version

    b = memory_service.upsert_record(
        db_session,
        source_type="note",
        source_id=2,
        content="Same content",
    )
    db_session.commit()
    assert b.id == a_id
    assert b.source_hash == a_hash
    assert b.version == a_version  # no rev when hash didn't change


def test_upsert_changed_content_bumps_version_and_rechunks(db_session):
    a = memory_service.upsert_record(
        db_session,
        source_type="note",
        source_id=3,
        content="Original content with words.",
    )
    db_session.commit()
    # Capture before the next upsert mutates the same row in place.
    initial_id = a.id
    initial_version = a.version
    initial_hash = a.source_hash

    b = memory_service.upsert_record(
        db_session,
        source_type="note",
        source_id=3,
        content="Different content entirely with new tokens.",
    )
    db_session.commit()
    assert b.id == initial_id
    assert b.source_hash != initial_hash
    assert b.version == initial_version + 1

    chunks = (
        db_session.query(SemanticChunk)
        .filter_by(memory_record_id=b.id)
        .all()
    )
    # Chunks reflect the NEW source_hash, not the old one.
    assert all(c.source_hash == b.source_hash for c in chunks)
