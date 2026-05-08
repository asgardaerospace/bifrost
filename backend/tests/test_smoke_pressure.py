"""Sprint 2 — pressure engine: deterministic compute + persisted history."""

from __future__ import annotations


def _make_mission(client, **kwargs):
    payload = {"codename": kwargs.pop("codename", "PRESS-1"), "name": "Pressure mission"}
    payload.update(kwargs)
    return client.post("/api/v1/missions", json=payload).json()


def test_pressure_baseline_for_normal_priority(client):
    m = _make_mission(client, codename="PRESS-NORMAL")
    r = client.get(f"/api/v1/missions/{m['id']}/pressure")
    assert r.status_code == 200
    body = r.json()
    # base + activity (1 mission.created event) + a single trigger. Should be low.
    assert 0 <= body["pressure_score"] < 35
    assert body["health_status"] in {"nominal", "watch"}
    assert "components" in body
    assert "blockers" in body["components"]
    assert "high_priority_intel" in body["components"]


def test_pressure_history_records_snapshots(client):
    m = _make_mission(client, codename="PRESS-HIST")
    # Trigger several recomputes by mutating the mission.
    client.patch(
        f"/api/v1/missions/{m['id']}", json={"description": "first edit"}
    )
    client.patch(
        f"/api/v1/missions/{m['id']}", json={"description": "second edit"}
    )

    r = client.get(f"/api/v1/missions/{m['id']}/pressure/history")
    assert r.status_code == 200
    body = r.json()
    assert body["mission_id"] == m["id"]
    # mission.created + 2 mission.updated → at least 3 snapshots.
    assert body["count"] >= 3
    for snap in body["snapshots"]:
        assert 0 <= snap["score"] <= 100
        assert snap["health_status"] in {"nominal", "watch", "strain", "critical"}


def test_pressure_blocker_raises_score(client):
    m = _make_mission(client, codename="PRESS-BLOCK", priority="normal")

    # Add 2 blocked queue items linked to the mission.
    for i in range(2):
        client.post(
            "/api/v1/execution/actions",
            json={
                "item_type": "task",
                "title": f"Blocked task {i}",
                "mission_id": m["id"],
            },
        )
    # Mark them blocked via PATCH.
    queue = client.get(
        f"/api/v1/execution/queue?mission_id={m['id']}"
    ).json()["items"]
    persisted_ids = [it["id"] for it in queue if not it["is_projected"]]
    for item_id in persisted_ids[:2]:
        client.patch(
            f"/api/v1/execution/actions/{item_id}",
            json={"status": "blocked", "blocked_reason": "awaiting upstream"},
        )

    r = client.get(f"/api/v1/missions/{m['id']}/pressure")
    body = r.json()
    assert body["components"]["blockers"] >= 8  # 2 blockers × 8 pts/each
    assert body["pressure_score"] >= 8


def test_priority_critical_adds_base_pressure(client):
    base = _make_mission(client, codename="PRESS-CRIT", priority="critical")
    r = client.get(f"/api/v1/missions/{base['id']}/pressure")
    body = r.json()
    # Critical priority adds 15 to base. Score should be ≥ 15 even without other signals.
    assert body["components"]["base"] == 15
    assert body["pressure_score"] >= 15


def test_manual_recompute_creates_snapshot(client):
    m = _make_mission(client, codename="PRESS-MANUAL")
    # Drop history that was created by mission.created trigger
    before = client.get(f"/api/v1/missions/{m['id']}/pressure/history").json()["count"]
    r = client.post(f"/api/v1/missions/{m['id']}/pressure/recompute")
    assert r.status_code == 200
    snap = r.json()
    assert snap["source"] == "manual"
    after = client.get(f"/api/v1/missions/{m['id']}/pressure/history").json()["count"]
    assert after == before + 1
