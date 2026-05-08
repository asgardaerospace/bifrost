"""Sprint 5 — cognition pipeline: intent, retrieval planning, weak refusal."""

from __future__ import annotations

from app.services import cognition as cognition_service


def test_classify_intent_matches_curated_keywords():
    c = cognition_service.classify_intent("show missions under rising pressure")
    assert c is not None
    assert c.intent.intent_id == "missions_under_pressure"
    assert "rising pressure" in c.matched_keywords or "missions under pressure" in c.matched_keywords
    assert c.confidence > 0.4


def test_classify_intent_unknown_command():
    c = cognition_service.classify_intent("compose me a sonnet about engines")
    assert c is None


def test_cognition_command_unknown_returns_weak_refusal(client):
    r = client.post(
        "/api/v1/cognition/command",
        json={"command": "compose me a sonnet about engines"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent_id"] is None
    assert body["synthesis"]["weak_retrieval"] is True
    assert "INSUFFICIENT INTENT" in body["synthesis"]["summary"].upper()


def test_cognition_command_supplier_instability(client, db_session):
    from app.services import intel_ingest as ingest_service
    from app.services.intel_providers.aerospace_seed import aerospace_seed_signals

    # Seed an active mission whose vocabulary overlaps the supplier_risk signal.
    client.post(
        "/api/v1/missions",
        json={
            "codename": "COG-SUP",
            "name": "Supplier risk mission",
            "priority": "high",
            "status": "active",
            "description": "propulsion qualification static fire program",
        },
    )

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        ingest_service.ingest_batch(db, aerospace_seed_signals(), actor="test")
    finally:
        db.close()

    r = client.post(
        "/api/v1/cognition/command",
        json={"command": "summarize supplier instability"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent_id"] == "supplier_instability"
    assert body["synthesis"]["retrieval_trace"]["embedding_model"]
    # Either grounded with citations or graceful weak — never crashes.
    if not body["synthesis"]["weak_retrieval"]:
        assert body["synthesis"]["citations"]


def test_cognition_command_explain_pressure_requires_codename(client):
    r = client.post(
        "/api/v1/cognition/command",
        json={"command": "explain why pressure increased"},
    )
    body = r.json()
    # Missing codename → graceful refusal under the explain_pressure intent.
    assert body["intent_id"] == "explain_pressure"
    assert body["synthesis"]["weak_retrieval"] is True
    assert "INSUFFICIENT" in body["synthesis"]["summary"].upper()


def test_cognition_intents_endpoint(client):
    r = client.get("/api/v1/cognition/intents")
    assert r.status_code == 200
    body = r.json()
    ids = {i["intent_id"] for i in body}
    assert "missions_under_pressure" in ids
    assert "supplier_instability" in ids
    assert "explain_pressure" in ids
