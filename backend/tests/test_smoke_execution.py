"""Smoke 3 — Execution queue projects existing tasks + admits direct items."""

from __future__ import annotations

from app.models.task import Task


def test_queue_returns_empty_initially(client):
    r = client.get("/api/v1/execution/queue")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["items"] == []


def test_queue_projects_existing_tasks(client, db_session):
    # Insert a Task directly via ORM — the queue must project it without
    # a write to execution_queue_items (the adapter contract).
    task = Task(
        title="Verify static-fire safety review",
        description="Confirm range-safety officer sign-off before T-0.",
        status="open",
        priority="high",
    )
    db_session.add(task)
    db_session.commit()

    r = client.get("/api/v1/execution/queue")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1

    projected = next(
        (i for i in body["items"] if i["source_type"] == "task" and i["source_id"] == task.id),
        None,
    )
    assert projected is not None, "task should be projected into queue"
    assert projected["is_projected"] is True
    assert projected["item_type"] == "task"
    assert projected["title"] == "Verify static-fire safety review"
    assert projected["priority_score"] == 80  # high → 80


def test_queue_admits_direct_item_and_patches_status(client):
    r = client.post(
        "/api/v1/execution/actions",
        json={
            "item_type": "recommendation",
            "title": "Reach out to Lockheed Skunk Works re: bridge contract",
            "summary": "Recommended after intel signal #142.",
            "priority_score": 75,
        },
    )
    assert r.status_code == 201, r.text
    item = r.json()
    item_id = item["id"]
    assert item["is_projected"] is False
    assert item["status"] == "queued"

    r = client.patch(
        f"/api/v1/execution/actions/{item_id}",
        json={"status": "in_progress", "owner": "ops-1"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"
    assert r.json()["owner"] == "ops-1"

    r = client.get("/api/v1/execution/queue")
    assert any(
        i.get("id") == item_id and i["status"] == "in_progress" for i in r.json()["items"]
    )


def test_relationships_and_propagation(client):
    # Create two missions and link them.
    a = client.post(
        "/api/v1/missions", json={"codename": "ALPHA", "name": "Alpha"}
    ).json()
    b = client.post(
        "/api/v1/missions", json={"codename": "BRAVO", "name": "Bravo"}
    ).json()

    r = client.post(
        "/api/v1/graph/relationships",
        json={
            "source_type": "mission",
            "source_id": a["id"],
            "target_type": "mission",
            "target_id": b["id"],
            "relationship_type": "depends_on",
        },
    )
    assert r.status_code == 201, r.text

    # Propagation should reach BRAVO from ALPHA.
    r = client.get(
        "/api/v1/graph/propagation",
        params={
            "source_type": "mission",
            "source_id": a["id"],
            "direction": "downstream",
            "depth": 2,
        },
    )
    assert r.status_code == 200
    nodes = r.json()["nodes"]
    assert any(n["entity_id"] == b["id"] and n["entity_type"] == "mission" for n in nodes)

    # ALPHA dependencies should now include BRAVO downstream.
    r = client.get(f"/api/v1/missions/{a['id']}/dependencies")
    assert r.status_code == 200
    downstream_ids = [e["other_mission_id"] for e in r.json()["downstream"]]
    assert b["id"] in downstream_ids


def test_event_publish_and_stream(client):
    r = client.post(
        "/api/v1/events",
        json={
            "topic": "missions",
            "event_type": "mission.smoke_test",
            "severity": "info",
            "payload": {"hello": "bifrost"},
        },
    )
    assert r.status_code == 201
    last_id = r.json()["id"]

    r = client.get(
        "/api/v1/events", params={"topic": "missions", "since": 0}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert any(e["id"] == last_id for e in body["items"])

    # Cursor pagination — passing cursor back should yield empty.
    r2 = client.get(
        "/api/v1/events", params={"topic": "missions", "since": last_id}
    )
    assert r2.status_code == 200
    assert all(e["id"] > last_id for e in r2.json()["items"])
