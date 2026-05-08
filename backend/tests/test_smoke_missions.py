"""Smoke 2 — Mission CRUD + linkage + pressure + dependencies + timeline round-trip."""

from __future__ import annotations


def test_mission_crud_round_trip(client):
    # Create
    payload = {
        "codename": "STARLINE-1",
        "name": "Starline 1 — propulsion qualification",
        "description": "Qualify static-fire test article 1.",
        "mission_type": "program",
        "priority": "high",
    }
    r = client.post("/api/v1/missions", json=payload)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["codename"] == "STARLINE-1"
    assert created["status"] == "planning"
    assert created["health_status"] == "nominal"
    mission_id = created["id"]

    # Read
    r = client.get(f"/api/v1/missions/{mission_id}")
    assert r.status_code == 200
    assert r.json()["name"].startswith("Starline 1")

    # List filtered
    r = client.get("/api/v1/missions", params={"priority": "high"})
    assert r.status_code == 200
    assert any(m["id"] == mission_id for m in r.json())

    # Patch
    r = client.patch(
        f"/api/v1/missions/{mission_id}",
        json={"status": "active"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    # Pressure is now engine-derived (Sprint 2). The patch trigger recomputes
    # it, so we don't check the literal value — only that it's a valid score.
    assert 0 <= r.json()["pressure_score"] <= 100

    # Pressure (scaffold)
    r = client.get(f"/api/v1/missions/{mission_id}/pressure")
    assert r.status_code == 200
    pressure = r.json()
    assert pressure["mission_id"] == mission_id
    assert pressure["health_status"] in {"nominal", "watch", "strain", "critical"}
    assert "components" in pressure

    # Dependencies (empty for a fresh mission)
    r = client.get(f"/api/v1/missions/{mission_id}/dependencies")
    assert r.status_code == 200
    deps = r.json()
    assert deps == {"mission_id": mission_id, "upstream": [], "downstream": []}

    # Timeline (empty)
    r = client.get(f"/api/v1/missions/{mission_id}/timeline")
    assert r.status_code == 200
    tl = r.json()
    assert tl["count"] == 0
    assert tl["items"] == []

    # Link an arbitrary entity (additive)
    r = client.post(
        f"/api/v1/missions/{mission_id}/entities",
        json={
            "entity_type": "investor_opportunity",
            "entity_id": 42,
            "relationship_type": "primary",
        },
    )
    assert r.status_code == 201, r.text
    link_id = r.json()["id"]

    # Entities list
    r = client.get(f"/api/v1/missions/{mission_id}/entities")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["entity_type"] == "investor_opportunity"

    # Unlink
    r = client.delete(f"/api/v1/missions/{mission_id}/entities/{link_id}")
    assert r.status_code == 204

    # Soft delete
    r = client.delete(f"/api/v1/missions/{mission_id}")
    assert r.status_code == 204
    r = client.get(f"/api/v1/missions/{mission_id}")
    assert r.status_code == 404


def test_mission_codename_unique(client):
    r = client.post(
        "/api/v1/missions",
        json={"codename": "DUPLICATE", "name": "First"},
    )
    assert r.status_code == 201
    r2 = client.post(
        "/api/v1/missions",
        json={"codename": "DUPLICATE", "name": "Second"},
    )
    assert r2.status_code == 409
