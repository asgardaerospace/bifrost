"""Sprint 1 — events emitted on key actions."""

from __future__ import annotations


def _topics_and_types(client, since=0):
    r = client.get("/api/v1/events", params={"since": since, "limit": 200})
    items = r.json()["items"]
    return {(e["topic"], e["event_type"]) for e in items}, items[-1]["id"] if items else 0


def test_mission_lifecycle_events(client):
    # create
    r = client.post(
        "/api/v1/missions", json={"codename": "EVENT-1", "name": "Event mission"}
    )
    mission_id = r.json()["id"]

    # update
    client.patch(
        f"/api/v1/missions/{mission_id}", json={"status": "active"}
    )

    # link an entity
    client.post(
        f"/api/v1/missions/{mission_id}/entities",
        json={"entity_type": "investor_opportunity", "entity_id": 99},
    )

    pairs, _ = _topics_and_types(client)
    assert ("missions", "mission.created") in pairs
    assert ("missions", "mission.updated") in pairs
    assert ("missions", "mission.entity_linked") in pairs


def test_relationship_creation_emits_event(client):
    a = client.post(
        "/api/v1/missions", json={"codename": "REL-A", "name": "A"}
    ).json()
    b = client.post(
        "/api/v1/missions", json={"codename": "REL-B", "name": "B"}
    ).json()
    client.post(
        "/api/v1/graph/relationships",
        json={
            "source_type": "mission",
            "source_id": a["id"],
            "target_type": "mission",
            "target_id": b["id"],
            "relationship_type": "supports",
        },
    )
    pairs, _ = _topics_and_types(client)
    assert ("graph", "relationship.created") in pairs


def test_queue_item_completion_event(client):
    r = client.post(
        "/api/v1/execution/actions",
        json={
            "item_type": "recommendation",
            "title": "Quick task",
            "priority_score": 40,
        },
    )
    item_id = r.json()["id"]
    client.patch(
        f"/api/v1/execution/actions/{item_id}", json={"status": "completed"}
    )

    pairs, _ = _topics_and_types(client)
    assert ("execution", "queue.item_created") in pairs
    assert ("execution", "queue.item_completed") in pairs


def test_event_filtering_by_topic_and_mission(client):
    m = client.post(
        "/api/v1/missions",
        json={"codename": "FILTER-1", "name": "Filterable mission"},
    ).json()
    # Filter by topic="missions" and mission_id should return at least the create.
    r = client.get(
        "/api/v1/events",
        params={"topic": "missions", "mission_id": m["id"], "since": 0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert all(e["topic"] == "missions" for e in body["items"])
    assert all(e["mission_id"] == m["id"] for e in body["items"])
