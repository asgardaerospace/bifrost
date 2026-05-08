"""Sprint 3 — retrieval ranking, mission scope, temporal filter, weak retrieval."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services import memory as memory_service
from app.services import retrieval as retrieval_service


def _seed(db_session, *, source_id: int, content: str, mission_id=None,
          occurred_at=None):
    return memory_service.upsert_record(
        db_session,
        source_type="note",
        source_id=source_id,
        content=content,
        title=f"Note {source_id}",
        mission_id=mission_id,
        source_occurred_at=occurred_at,
    )


def test_search_ranks_by_token_overlap(db_session):
    _seed(db_session, source_id=10, content="propulsion qualification static fire")
    _seed(db_session, source_id=11, content="market campaign sector accounts")
    _seed(db_session, source_id=12, content="static fire propulsion test results")
    db_session.commit()

    results, trace = retrieval_service.search(
        db_session, query="propulsion static fire", limit=3
    )
    assert results
    # Top results should both be about propulsion.
    top_sources = [r.source_id for r in results[:2]]
    assert 10 in top_sources or 12 in top_sources
    # Market chunk should not lead.
    assert results[0].source_id != 11
    assert trace.embedding_model
    assert trace.candidates_considered >= 3


def test_search_mission_scoping(db_session):
    _seed(db_session, source_id=20, content="Capital raise prepared", mission_id=100)
    _seed(db_session, source_id=21, content="Capital raise prepared", mission_id=200)
    db_session.commit()

    results, trace = retrieval_service.search(
        db_session, query="capital raise", mission_id=100, limit=10
    )
    assert all(r.mission_id == 100 for r in results)
    assert trace.scoped_mission_id == 100


def test_search_temporal_filter(db_session):
    now = datetime.now(timezone.utc)
    _seed(
        db_session,
        source_id=30,
        content="recent activity propulsion",
        occurred_at=now - timedelta(days=1),
    )
    _seed(
        db_session,
        source_id=31,
        content="recent activity propulsion",
        occurred_at=now - timedelta(days=120),
    )
    db_session.commit()

    cutoff = now - timedelta(days=14)
    results, _ = retrieval_service.search(
        db_session, query="recent activity", since=cutoff, limit=10
    )
    sources = {r.source_id for r in results}
    assert 30 in sources
    assert 31 not in sources


def test_recency_weight_pushes_newer_higher(db_session):
    now = datetime.now(timezone.utc)
    _seed(
        db_session,
        source_id=40,
        content="approval requested for supplier contract",
        occurred_at=now - timedelta(days=1),
    )
    _seed(
        db_session,
        source_id=41,
        content="approval requested for supplier contract",
        occurred_at=now - timedelta(days=180),
    )
    db_session.commit()

    results, _ = retrieval_service.search(
        db_session, query="approval requested supplier", limit=2
    )
    # Same semantic + keyword score; recency should break the tie toward 40.
    assert results[0].source_id == 40


def test_weak_retrieval_when_no_overlap(db_session):
    _seed(db_session, source_id=50, content="completely unrelated subject material")
    db_session.commit()

    results, _ = retrieval_service.search(
        db_session, query="quantum entanglement aerospace", limit=5
    )
    # Threshold is 0.15. Pure mismatch should fall below.
    assert retrieval_service.is_weak(results) or results == []


def test_score_components_present_and_explainable(db_session):
    _seed(db_session, source_id=60, content="explainable retrieval components test")
    db_session.commit()

    results, _ = retrieval_service.search(
        db_session, query="explainable retrieval", limit=1
    )
    assert results
    comps = results[0].components
    for k in ("semantic", "keyword", "recency", "w_semantic", "w_keyword", "w_recency"):
        assert k in comps
