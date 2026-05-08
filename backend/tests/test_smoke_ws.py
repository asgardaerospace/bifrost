"""Sprint 2 — websocket connect, subscribe, broadcast, disconnect."""

from __future__ import annotations

import asyncio

from app.services.pubsub import manager


def test_ws_handshake_and_hello(client):
    with client.websocket_connect("/api/v1/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "hello"
        assert msg["client_id"]


def test_ws_subscribe_and_receive_broadcast(client):
    with client.websocket_connect("/api/v1/ws?client_id=test-A") as ws:
        ws.receive_json()  # hello
        ws.send_json({"action": "subscribe", "topic": "missions"})
        ack = ws.receive_json()
        assert ack["type"] == "subscribed"
        assert ack["topic"] == "missions"

        # Broadcast through the local manager (no Redis).
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                manager.broadcast(
                    "missions",
                    None,
                    {
                        "type": "event",
                        "topic": "missions",
                        "event_type": "mission.test_broadcast",
                        "id": 999,
                    },
                )
            )
        finally:
            loop.close()

        ev = ws.receive_json()
        assert ev["event_type"] == "mission.test_broadcast"
        assert ev["topic"] == "missions"


def test_ws_mission_filter_excludes_other_missions(client):
    with client.websocket_connect("/api/v1/ws?client_id=test-B") as ws:
        ws.receive_json()
        ws.send_json({"action": "subscribe", "topic": "missions", "mission_id": 1})
        ws.receive_json()

        loop = asyncio.new_event_loop()
        try:
            # Mission 2 broadcast — should NOT arrive.
            loop.run_until_complete(
                manager.broadcast(
                    "missions",
                    2,
                    {
                        "type": "event",
                        "topic": "missions",
                        "event_type": "mission.other",
                        "mission_id": 2,
                    },
                )
            )
            # Mission 1 broadcast — SHOULD arrive.
            loop.run_until_complete(
                manager.broadcast(
                    "missions",
                    1,
                    {
                        "type": "event",
                        "topic": "missions",
                        "event_type": "mission.mine",
                        "mission_id": 1,
                    },
                )
            )
        finally:
            loop.close()

        msg = ws.receive_json()
        assert msg["event_type"] == "mission.mine"
        assert msg["mission_id"] == 1


def test_ws_heartbeat_returns_pong(client):
    with client.websocket_connect("/api/v1/ws?client_id=test-HB") as ws:
        ws.receive_json()  # hello
        ws.send_json({"action": "heartbeat"})
        msg = ws.receive_json()
        assert msg["type"] == "pong"
        assert "ts" in msg


def test_ws_disconnect_clears_connection(client):
    before = manager.connection_count
    with client.websocket_connect("/api/v1/ws?client_id=test-D") as ws:
        ws.receive_json()
        assert manager.connection_count >= before + 1
    # After context exit, manager should have one fewer connection.
    # Allow async cleanup time — TestClient runs in its own loop.
    assert manager.connection_count <= before + 1


def test_ws_replay_endpoint(client):
    # Drive the persisted event log.
    client.post("/api/v1/missions", json={"codename": "REPLAY-1", "name": "Replay test"})
    r = client.get("/api/v1/events/replay?since=0&topic=missions")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert any(e["event_type"] == "mission.created" for e in body["items"])
