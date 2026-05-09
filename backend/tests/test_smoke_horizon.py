"""Sprint 7 smoke — executive horizon, environment, topology, operational timeline."""

from __future__ import annotations


def _make_mission(client, **kwargs):
    payload = {
        "codename": kwargs.pop("codename", "S7-HORIZON-1"),
        "name": kwargs.pop("name", "Horizon mission"),
    }
    payload.update(kwargs)
    return client.post("/api/v1/missions", json=payload).json()


def test_horizon_endpoint_returns_view(client):
    _make_mission(client, codename="HZN-A")
    _make_mission(client, codename="HZN-B", priority="critical")
    r = client.get("/api/v1/horizon")
    assert r.status_code == 200
    body = r.json()
    assert "headline" in body
    assert body["band"] in {"nominal", "watch", "strain", "critical"}
    assert "pressure_map" in body
    pm = body["pressure_map"]
    for k in ("nominal", "watch", "strain", "critical", "average_score", "peak_score"):
        assert k in pm
    assert "tempo" in body
    assert "events_last_hour" in body["tempo"]
    assert isinstance(body["top_missions"], list)
    assert isinstance(body["escalations"], list)
    assert isinstance(body["opportunities"], list)
    assert isinstance(body["narrative"], list)
    assert len(body["narrative"]) >= 1


def test_horizon_top_missions_capped(client):
    for i in range(5):
        _make_mission(client, codename=f"HZN-CAP-{i}")
    r = client.get("/api/v1/horizon?top_n=2")
    assert r.status_code == 200
    body = r.json()
    assert len(body["top_missions"]) <= 2


def test_environment_endpoint_returns_snapshot(client):
    r = client.get("/api/v1/environment")
    assert r.status_code == 200
    body = r.json()
    assert "pulse" in body
    pulse = body["pulse"]
    for k in (
        "band",
        "pressure_index",
        "propagation_index",
        "activity_rate",
        "escalation_count",
    ):
        assert k in pulse
    assert pulse["band"] in {"calm", "active", "elevated", "critical"}
    assert 0 <= pulse["pressure_index"] <= 100
    assert "trend" in body
    assert "pulses" in body["trend"]
    assert isinstance(body["narrative"], list)


def test_environment_trend_accumulates(client):
    # Multiple calls should populate the in-process ring buffer; no crash,
    # values stay in [0,100], pulses count grows.
    for _ in range(3):
        r = client.get("/api/v1/environment")
        assert r.status_code == 200
    body = r.json()
    assert len(body["trend"]["pulses"]) >= 1
    for p in body["trend"]["pulses"]:
        assert 0 <= p["pressure_index"] <= 100
        assert 0 <= p["propagation_index"] <= 100


def test_topology_org_view(client):
    a = _make_mission(client, codename="TOPO-A")
    b = _make_mission(client, codename="TOPO-B")
    # Create a mission ↔ mission edge
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
    r = client.get("/api/v1/topology")
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == "org"
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)
    # Both missions should appear as nodes.
    node_ids = {n["id"] for n in body["nodes"]}
    assert f"mission:{a['id']}" in node_ids
    assert f"mission:{b['id']}" in node_ids
    # The depends_on edge should appear.
    edge_kinds = {e["kind"] for e in body["edges"]}
    assert "depends_on" in edge_kinds
    assert "cluster_summary" in body


def test_topology_mission_scope(client):
    a = _make_mission(client, codename="TOPO-MS-A")
    r = client.get(f"/api/v1/missions/{a['id']}/topology")
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == "mission"
    assert body["mission_id"] == a["id"]


def test_operational_timeline_returns_entries(client):
    m = _make_mission(client, codename="TIMELINE-1")
    # Mutate to create more events.
    client.patch(f"/api/v1/missions/{m['id']}", json={"description": "edit"})
    r = client.get("/api/v1/operational-timeline?hours=24")
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == "org"
    assert "entries" in body
    assert "counts_by_kind" in body
    assert "counts_by_severity" in body
    # We made a mission and patched it — we should have operational events.
    assert body["count"] >= 1
    kinds = {e["kind"] for e in body["entries"]}
    assert "operational_event" in kinds


def test_mission_operational_timeline_scope(client):
    m = _make_mission(client, codename="TIMELINE-MS")
    r = client.get(f"/api/v1/missions/{m['id']}/operational-timeline?hours=72")
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == "mission"
    assert body["mission_id"] == m["id"]
    for e in body["entries"]:
        assert e["mission_id"] == m["id"] or e["mission_id"] is None


def test_operational_timeline_window_accepted(client):
    r = client.get("/api/v1/operational-timeline?hours=6&limit=10")
    assert r.status_code == 200
    body = r.json()
    assert len(body["entries"]) <= 10


def test_operational_timeline_clusters_only_for_repeats(client):
    """Empty / single-entry windows should produce zero clusters."""
    r = client.get("/api/v1/operational-timeline?hours=1&limit=10")
    assert r.status_code == 200
    body = r.json()
    # All clusters reported must have at least 2 entries per service contract.
    for c in body["clusters"]:
        assert c["entry_count"] >= 2
