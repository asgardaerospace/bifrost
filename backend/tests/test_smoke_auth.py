"""Sprint 1 — auth foundation: anonymous when enforcement off, JWT round-trip."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User


def test_me_returns_anonymous_when_enforcement_off(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["is_anonymous"] is True
    assert body["primary_role"] == "anonymous"


def test_login_dev_mode_email_only(client, db_session):
    # Seed a user without password_hash; in dev mode email-only login works.
    db_session.add(
        User(
            email="ops@asgard.local",
            name="Ops Operator",
            primary_role="operator",
        )
    )
    db_session.commit()

    r = client.post(
        "/api/v1/auth/login", json={"email": "ops@asgard.local"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "ops@asgard.local"
    assert body["user"]["has_password"] is False


def test_login_with_password_hash(client, db_session):
    db_session.add(
        User(
            email="exec@asgard.local",
            name="Exec",
            primary_role="executive",
            password_hash=hash_password("hunter2"),
        )
    )
    db_session.commit()

    # Wrong password
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "exec@asgard.local", "password": "wrong"},
    )
    assert r.status_code == 401

    # Right password
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "exec@asgard.local", "password": "hunter2"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    # /auth/me with bearer should resolve to the real user.
    r2 = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["is_anonymous"] is False
    assert body["email"] == "exec@asgard.local"
    assert body["primary_role"] == "executive"


def test_enforcement_on_blocks_anonymous(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enforcement_enabled", True)

    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"

    monkeypatch.setattr(settings, "auth_enforcement_enabled", False)
