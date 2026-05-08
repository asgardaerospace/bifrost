"""Sprint 1 — governance: approval gates queue completion."""

from __future__ import annotations


def test_requires_approval_blocks_completion(client):
    # Create a queue item that requires approval.
    r = client.post(
        "/api/v1/execution/actions",
        json={
            "item_type": "recommendation",
            "title": "Send investor brief to Lockheed",
            "summary": "Approval-gated outbound communication.",
            "priority_score": 70,
            "requires_approval": True,
        },
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["requires_approval"] is True
    item_id = item["id"]

    # Attempting to mark completed should be rejected with 409.
    r = client.patch(
        f"/api/v1/execution/actions/{item_id}",
        json={"status": "completed"},
    )
    assert r.status_code == 409
    assert "approval" in r.json()["detail"].lower()


def test_approval_unlocks_completion(client):
    r = client.post(
        "/api/v1/execution/actions",
        json={
            "item_type": "recommendation",
            "title": "Reprioritize Mars 1 mission",
            "priority_score": 80,
            "requires_approval": True,
        },
    )
    item = r.json()
    item_id = item["id"]

    # Decide approved on the latest pending Approval for this queue item.
    r = client.post(
        f"/api/v1/execution/actions/{item_id}/decide",
        params={"decision": "approved"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    # Now status=completed should succeed.
    r = client.patch(
        f"/api/v1/execution/actions/{item_id}",
        json={"status": "completed"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"
    assert r.json()["completed_at"] is not None


def test_approval_creation_emits_event(client):
    # Create approval-gated item and verify approval.requested event was published.
    r = client.post(
        "/api/v1/execution/actions",
        json={
            "item_type": "recommendation",
            "title": "External press release",
            "requires_approval": True,
        },
    )
    assert r.status_code == 201

    # Check events stream — should include queue.item_created + approval.requested.
    r = client.get("/api/v1/events", params={"since": 0, "limit": 50})
    assert r.status_code == 200
    types = {e["event_type"] for e in r.json()["items"]}
    assert "queue.item_created" in types
    assert "approval.requested" in types


def test_decide_emits_approved_event(client):
    r = client.post(
        "/api/v1/execution/actions",
        json={
            "item_type": "recommendation",
            "title": "Audit log dump",
            "requires_approval": True,
        },
    )
    item_id = r.json()["id"]
    client.post(
        f"/api/v1/execution/actions/{item_id}/decide",
        params={"decision": "approved", "note": "verified"},
    )

    r = client.get(
        "/api/v1/events", params={"topic": "approvals", "since": 0, "limit": 50}
    )
    types = {e["event_type"] for e in r.json()["items"]}
    assert "approval.approved" in types


def test_decide_rejected_emits_rejected_event(client):
    r = client.post(
        "/api/v1/execution/actions",
        json={
            "item_type": "recommendation",
            "title": "Risky budget reallocation",
            "requires_approval": True,
        },
    )
    item_id = r.json()["id"]
    client.post(
        f"/api/v1/execution/actions/{item_id}/decide",
        params={"decision": "rejected"},
    )

    r = client.get("/api/v1/events", params={"topic": "approvals", "since": 0, "limit": 50})
    types = {e["event_type"] for e in r.json()["items"]}
    assert "approval.rejected" in types
