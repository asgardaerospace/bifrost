"""Sprint 5 — simulation: explainable, deterministic propagation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _make_mission(client, **kwargs):
    payload = {"codename": kwargs.pop("codename", "SIM-1"), "name": "Sim mission"}
    payload.update(kwargs)
    return client.post("/api/v1/missions", json=payload).json()


def test_supplier_failure_finds_directly_linked_missions(client):
    m = _make_mission(client, codename="SIM-DIRECT", priority="high")
    client.post(
        f"/api/v1/missions/{m['id']}/entities",
        json={"entity_type": "supplier", "entity_id": 99},
    )
    r = client.post(
        "/api/v1/simulations/supplier-failure", json={"supplier_id": 99}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["simulation_type"] == "supplier_failure"
    assert any(im["mission_id"] == m["id"] for im in body["impacted_missions"])
    assert body["pressure_deltas"][str(m["id"])] >= 12
    assert body["confidence"] > 0
    assert body["assumptions"]


def test_supplier_failure_unmonitored_returns_low_confidence(client):
    r = client.post(
        "/api/v1/simulations/supplier-failure", json={"supplier_id": 9999}
    )
    body = r.json()
    assert body["impacted_missions"] == []
    assert body["confidence"] <= 0.5
    assert body["notes"]  # explanation present


def test_approval_delay_simulation_returns_pressure_delta(client, db_session):
    from app.models.approval import Approval

    m = _make_mission(client, codename="SIM-APPR", priority="high")
    a = Approval(
        entity_type="generic",
        entity_id=1,
        action="execute_test",
        status="pending",
        mission_id=m["id"],
        requested_by="ops",
    )
    db_session.add(a)
    db_session.commit()

    r = client.post(
        "/api/v1/simulations/approval-delay",
        json={"approval_id": a.id, "delay_hours": 48},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["impacted_missions"]
    assert body["pressure_deltas"][str(m["id"])] >= 3
    assert body["confidence"] > 0


def test_dependency_propagation_walks_relationships(client):
    a = _make_mission(client, codename="SIM-A")
    b = _make_mission(client, codename="SIM-B")
    client.post(
        "/api/v1/graph/relationships",
        json={
            "source_type": "mission",
            "source_id": a["id"],
            "target_type": "mission",
            "target_id": b["id"],
            "relationship_type": "depends_on",
        },
    )
    r = client.post(
        "/api/v1/simulations/dependency-propagation",
        json={"entity_type": "mission", "entity_id": a["id"], "depth": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["propagation_paths"]
    # B should appear as an impacted mission.
    assert any(im["mission_id"] == b["id"] for im in body["impacted_missions"])
    assert body["assumptions"]
