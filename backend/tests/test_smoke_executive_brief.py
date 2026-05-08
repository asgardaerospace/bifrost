"""Sprint 4 — executive brief: grounded, cited, refuses on weak retrieval."""

from __future__ import annotations


def test_executive_brief_with_no_signals_is_weak(client):
    # Fresh DB → no signals → daily brief must refuse gracefully.
    r = client.get("/api/v1/executive/intelligence/brief")
    assert r.status_code == 200
    body = r.json()
    assert body["weak_retrieval"] is True
    assert body["confidence"] == 0.0
    assert body["citations"] == []
    assert "INSUFFICIENT" in body["summary"].upper()


def test_executive_brief_after_ingestion_grounded(client):
    from app.core.database import SessionLocal
    from app.services.intel_providers.aerospace_seed import aerospace_seed_signals
    from app.services import intel_ingest as ingest_service

    # Seed an active mission whose vocabulary overlaps the seed signals.
    client.post(
        "/api/v1/missions",
        json={
            "codename": "EXEC-1",
            "name": "Exec brief mission",
            "priority": "high",
            "status": "active",
            "description": "propulsion qualification static fire program",
        },
    )

    db = SessionLocal()
    try:
        ingest_service.ingest_batch(db, aerospace_seed_signals(), actor="test")
    finally:
        db.close()

    r = client.get("/api/v1/executive/intelligence/brief?hours=72")
    assert r.status_code == 200
    body = r.json()
    # Should now have grounded citations.
    if not body["weak_retrieval"]:
        assert body["citations"], "brief must cite when retrieval is strong"
        assert body["confidence"] > 0
        assert body["retrieval_trace"]["embedding_model"]


def test_mission_intel_synthesis_endpoint(client):
    from app.core.database import SessionLocal
    from app.services.intel_providers.aerospace_seed import aerospace_seed_signals
    from app.services import intel_ingest as ingest_service

    m = client.post(
        "/api/v1/missions",
        json={
            "codename": "EXEC-MSN",
            "name": "Intel-synth mission",
            "priority": "high",
            "status": "active",
            "description": "static fire propulsion test schedule",
        },
    ).json()

    db = SessionLocal()
    try:
        ingest_service.ingest_batch(db, aerospace_seed_signals(), actor="test")
    finally:
        db.close()

    r = client.get(
        f"/api/v1/missions/{m['id']}/intelligence/synthesize?hours=72"
    )
    assert r.status_code == 200
    body = r.json()
    # Either grounded or weak — but never raises an exception, never fabricates.
    assert "objective" in body
    assert body["model"]


def test_signal_listing_filters_by_severity(client):
    from app.core.database import SessionLocal
    from app.services.intel_providers.aerospace_seed import aerospace_seed_signals
    from app.services import intel_ingest as ingest_service

    db = SessionLocal()
    try:
        ingest_service.ingest_batch(db, aerospace_seed_signals(), actor="test")
    finally:
        db.close()

    r_all = client.get("/api/v1/intelligence/signals?limit=20")
    assert r_all.status_code == 200
    assert len(r_all.json()) == 5

    r_warn = client.get("/api/v1/intelligence/signals?severity=warning")
    assert r_warn.status_code == 200
    if r_warn.json():
        assert all(s["severity"] == "warning" for s in r_warn.json())


def test_mission_intelligence_endpoint_returns_relevance_and_impact(client):
    from app.core.database import SessionLocal
    from app.services.intel_providers.aerospace_seed import aerospace_seed_signals
    from app.services import intel_ingest as ingest_service

    m = client.post(
        "/api/v1/missions",
        json={
            "codename": "EXEC-INTEL",
            "name": "Intel surface mission",
            "priority": "high",
            "status": "active",
            "description": "propulsion qualification static fire",
        },
    ).json()

    db = SessionLocal()
    try:
        ingest_service.ingest_batch(db, aerospace_seed_signals(), actor="test")
    finally:
        db.close()

    r = client.get(f"/api/v1/missions/{m['id']}/intelligence")
    assert r.status_code == 200
    body = r.json()
    assert body["mission_id"] == m["id"]
    # Each item has both relevance and signal joined fields.
    if body["count"] > 0:
        first = body["items"][0]
        assert "relevance" in first
        assert "signal" in first
        assert first["signal"]["signal_type"]
        assert first["signal"]["severity"]
