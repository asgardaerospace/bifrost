"""Sprint 2 — presence sessions: register, heartbeat, list, prune."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.presence import PresenceSession
from app.services import presence as presence_service


def test_register_and_list_active(client, db_session):
    presence_service.register_or_refresh(
        db_session,
        client_id="op-1",
        display_name="Operator One",
        mission_id=None,
    )
    presence_service.register_or_refresh(
        db_session,
        client_id="op-2",
        display_name="Operator Two",
        mission_id=42,
    )

    r = client.get("/api/v1/presence/active")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    emails = {o["display_name"] for o in body["operators"]}
    assert {"Operator One", "Operator Two"} <= emails


def test_mission_scoped_presence(client, db_session):
    presence_service.register_or_refresh(
        db_session, client_id="m1-a", display_name="A", mission_id=1
    )
    presence_service.register_or_refresh(
        db_session, client_id="m1-b", display_name="B", mission_id=1
    )
    presence_service.register_or_refresh(
        db_session, client_id="m2-c", display_name="C", mission_id=2
    )

    r = client.get("/api/v1/presence/mission/1")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert all(o["mission_id"] == 1 for o in body["operators"])


def test_disconnect_removes_from_active(client, db_session):
    presence_service.register_or_refresh(
        db_session, client_id="goneSoon", display_name="X", mission_id=None
    )
    presence_service.disconnect(db_session, client_id="goneSoon")

    r = client.get("/api/v1/presence/active")
    assert all(o["client_id"] != "goneSoon" for o in r.json()["operators"])


def test_stale_sessions_pruned(client, db_session):
    # Manually insert a stale session past TTL.
    old = PresenceSession(
        client_id="stale-1",
        display_name="Stale",
        mission_id=None,
        connected_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        last_heartbeat=datetime.now(timezone.utc) - timedelta(minutes=5),
        disconnected_at=None,
    )
    db_session.add(old)
    db_session.commit()

    # The route prunes before listing.
    r = client.get("/api/v1/presence/active")
    assert all(o["client_id"] != "stale-1" for o in r.json()["operators"])
