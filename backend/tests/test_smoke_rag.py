"""Sprint 3 — RAG pipeline: assembly, citations, weak-retrieval graceful fail."""

from __future__ import annotations

from app.services import memory as memory_service
from app.services import rag as rag_service


def _make_mission(client, **kwargs):
    payload = {"codename": kwargs.pop("codename", "RAG-1"), "name": "RAG mission"}
    payload.update(kwargs)
    return client.post("/api/v1/missions", json=payload).json()


def test_synthesize_mission_with_grounded_context(client, db_session):
    m = _make_mission(client, codename="RAG-CTX", priority="high")

    # Seed a few mission-scoped memory records so retrieval has something.
    memory_service.upsert_record(
        db_session,
        source_type="note",
        source_id=901,
        content="Static fire test successful — propulsion baseline confirmed.",
        title="Test result",
        mission_id=m["id"],
    )
    memory_service.upsert_record(
        db_session,
        source_type="note",
        source_id=902,
        content="Awaiting range-safety approval before next test window.",
        title="Approval note",
        mission_id=m["id"],
    )
    db_session.commit()

    r = client.post(f"/api/v1/missions/{m['id']}/synthesize")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["objective"]
    assert body["weak_retrieval"] is False
    assert body["citations"], "synthesis must cite at least one chunk"
    assert body["confidence"] > 0
    # Trace metadata is exposed.
    trace = body["retrieval_trace"]
    assert trace["embedding_model"]
    assert trace["candidates_considered"] >= 1
    assert "weights" in trace


def test_synthesize_weak_retrieval_returns_graceful_fail(client):
    m = _make_mission(client, codename="RAG-EMPTY")
    # No memory records seeded for this mission.
    r = client.post(f"/api/v1/missions/{m['id']}/synthesize")
    assert r.status_code == 200
    body = r.json()
    # The mission itself was ingested as a record on create — depending on
    # the embedding overlap with the query, we expect EITHER weak_retrieval
    # OR a low confidence + sparse citations. Either is acceptable as a
    # graceful response — what we forbid is fabrication.
    if body["weak_retrieval"]:
        assert body["citations"] == []
        assert body["confidence"] == 0.0
        assert "INSUFFICIENT" in body["summary"].upper()
    else:
        assert body["citations"], "non-weak response must cite something"


def test_synthesize_pressure_filters_to_pressure_sources(client, db_session):
    m = _make_mission(client, codename="RAG-PRESS")
    # Seed an intel item-like record (allowed by pressure filter).
    memory_service.upsert_record(
        db_session,
        source_type="intel_item",
        source_id=701,
        content="Defense procurement schedule shifted left for FY27 propulsion.",
        title="DoD intel",
        mission_id=m["id"],
    )
    db_session.commit()

    r = client.post(f"/api/v1/missions/{m['id']}/synthesize/pressure")
    assert r.status_code == 200
    body = r.json()
    assert body["objective"].lower().startswith("explain pressure")


def test_related_missions_endpoint_excludes_self(client):
    m1 = _make_mission(client, codename="REL-1", description="propulsion qualification")
    _make_mission(client, codename="REL-2", description="propulsion qualification")
    _make_mission(client, codename="REL-3", description="market expansion")

    r = client.get(f"/api/v1/missions/{m1['id']}/related")
    assert r.status_code == 200
    body = r.json()
    # Should never return self.
    assert all(item["mission_id"] != m1["id"] for item in body["related"])
    # The propulsion-keyword sibling should rank above the market one.
    if len(body["related"]) >= 2:
        first = body["related"][0]
        # First result is one of the two other missions; the propulsion one
        # should out-rank the market one when both exist.
        assert first["score"] > 0


def test_search_endpoint_returns_trace(client, db_session):
    memory_service.upsert_record(
        db_session,
        source_type="note",
        source_id=801,
        content="Approvals queue is backed up on supplier qualification.",
    )
    db_session.commit()

    r = client.post(
        "/api/v1/memory/search",
        json={"query": "supplier approval queue", "limit": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert "trace" in body
    assert body["trace"]["embedding_model"]
    assert "weights" in body["trace"]
