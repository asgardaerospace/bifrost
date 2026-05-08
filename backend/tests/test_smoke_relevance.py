"""Sprint 4 — relevance engine + propagation + pressure integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.intel import IntelEntity, IntelItem
from app.models.mission import Mission, MissionEntity
from app.models.signal import SignalImpact, SignalRelevance
from app.services import relevance as relevance_service
from app.services import signal_propagation as signal_propagation_service
from app.services import signals as signal_helpers


def _make_mission(client, **kwargs):
    payload = {
        "codename": kwargs.pop("codename", "REL-1"),
        "name": kwargs.pop("name", "Relevance mission"),
        "priority": "high",
        "status": "active",
    }
    payload.update(kwargs)
    return client.post("/api/v1/missions", json=payload).json()


def _seed_intel(db_session, **kwargs) -> IntelItem:
    base = dict(
        source="TestFeed",
        title="Test signal",
        url="https://example/1",
        category="uncategorized",
        published_at=datetime.now(timezone.utc),
        summary="A test signal body",
        strategic_relevance_score=50,
        urgency_score=40,
        confidence_score=70,
    )
    base.update(kwargs)
    item = IntelItem(**base)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def test_direct_mission_link_dominates_relevance(client, db_session):
    m = _make_mission(client, codename="REL-LINK")
    mission = db_session.get(Mission, m["id"])
    item = _seed_intel(
        db_session,
        category="defense_tech",
        title="USAF awards propulsion contract",
        mission_id=m["id"],
    )

    result = relevance_service.compute(db_session, item=item, mission=mission)
    assert result.score >= 60
    assert result.is_relevant
    assert result.components["direct_mission_link"] == relevance_service.W_DIRECT_MISSION_LINK


def test_keyword_overlap_drives_relevance(client, db_session):
    m = _make_mission(
        client,
        codename="REL-KW",
        description="propulsion qualification static fire program",
    )
    mission = db_session.get(Mission, m["id"])
    item = _seed_intel(
        db_session,
        title="Static fire anomaly halts propulsion test cadence",
        summary="propulsion qualification static fire delay",
        category="aerospace_manufacturing",
    )
    result = relevance_service.compute(db_session, item=item, mission=mission)
    assert result.components["keyword_overlap"] > 0


def test_unrelated_signal_below_threshold(client, db_session):
    m = _make_mission(client, codename="REL-NO", description="capital raise series B")
    mission = db_session.get(Mission, m["id"])
    item = _seed_intel(
        db_session,
        title="HiTemp Composites Files Chapter 11",
        summary="supplier bankruptcy filing",
        category="supply_chain",
        strategic_relevance_score=20,
        urgency_score=15,
    )
    result = relevance_service.compute(db_session, item=item, mission=mission)
    # Capital-focused mission with no supplier link / no propulsion text:
    # score should not clear the relevance threshold.
    assert result.is_relevant is False


def test_supplier_overlap_boosts_score(client, db_session):
    m = _make_mission(client, codename="REL-SUP")
    # Link mission to supplier #42.
    client.post(
        f"/api/v1/missions/{m['id']}/entities",
        json={"entity_type": "supplier", "entity_id": 42},
    )
    mission = db_session.get(Mission, m["id"])

    item = _seed_intel(
        db_session,
        title="HiTemp Composites delivery delays",
        summary="supplier risk",
        category="supply_chain",
    )
    db_session.add(
        IntelEntity(
            intel_item_id=item.id,
            entity_type="supplier",
            entity_name="HiTemp Composites",
            entity_id=42,
        )
    )
    db_session.commit()

    result = relevance_service.compute(db_session, item=item, mission=mission)
    assert result.components["supplier_overlap"] > 0


def test_propagation_creates_impact_rows_for_relevant_signals(client, db_session):
    from app.services.intel_providers.aerospace_seed import aerospace_seed_signals
    from app.services import intel_ingest as ingest_service

    # Create a mission whose vocabulary matches the seed signals.
    m = _make_mission(
        client,
        codename="REL-PROP",
        description="propulsion qualification static fire program",
    )

    ingest_service.ingest_batch(db_session, aerospace_seed_signals(), actor="test")

    # Some signal should now have an impact row tied to this mission.
    impacts = signal_propagation_service.list_impacts_for_mission(db_session, m["id"])
    assert len(impacts) >= 1
    types = {imp.impact_type for imp in impacts}
    # Expect at least one of: raises_pressure, opportunity, informational.
    assert types & {"raises_pressure", "opportunity", "informational"}


def test_pressure_includes_signal_impact_component(client, db_session):
    from app.services.intel_providers.aerospace_seed import aerospace_seed_signals
    from app.services import intel_ingest as ingest_service

    m = _make_mission(
        client,
        codename="REL-PRESS",
        description="propulsion qualification static fire program",
    )
    ingest_service.ingest_batch(db_session, aerospace_seed_signals(), actor="test")

    r = client.get(f"/api/v1/missions/{m['id']}/pressure")
    assert r.status_code == 200
    body = r.json()
    assert "signal_impact" in body["components"]
    # Even if the value happens to be zero for this fixture, the breakdown
    # must be present so the operator can audit.
    assert "signal_breakdown" in body["components"]


def test_pressure_recompute_includes_signals_via_route(client):
    from app.services.intel_providers.aerospace_seed import aerospace_seed_signals
    from app.services import intel_ingest as ingest_service
    from app.core.database import SessionLocal

    m_resp = client.post(
        "/api/v1/missions",
        json={
            "codename": "REL-RECOMP",
            "name": "Recompute test",
            "priority": "high",
            "status": "active",
            "description": "propulsion qualification static fire",
        },
    )
    assert m_resp.status_code == 201
    mid = m_resp.json()["id"]

    db = SessionLocal()
    try:
        ingest_service.ingest_batch(db, aerospace_seed_signals(), actor="test")
    finally:
        db.close()

    r = client.post(f"/api/v1/missions/{mid}/pressure/recompute")
    assert r.status_code == 200
    snap = r.json()
    # Component breakdown is persisted on the snapshot too.
    assert "signal_impact" in snap["components"]
