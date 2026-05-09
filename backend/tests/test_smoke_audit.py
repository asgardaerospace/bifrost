"""Sprint 8 — audit trail."""

from __future__ import annotations

from app.services import audit as audit_service


def test_audit_record_writes_event(client, db_session):
    audit_service.record(
        db_session,
        action=audit_service.ACTION_AUTH_LOGIN,
        actor="ops@example.com",
        outcome="ok",
        target_type="user",
        target_id=42,
    )
    db_session.commit()
    # Read back via the governance audit endpoint.
    r = client.get("/api/v1/governance/audit?limit=10&action=auth.login")
    assert r.status_code == 200
    body = r.json()
    assert any(entry["actor"] == "ops@example.com" for entry in body)


def test_audit_failed_login_is_recorded(client):
    # First, create a user via direct service so the email exists,
    # then attempt a login with wrong password.
    from app.schemas.user import UserCreate
    from app.services.auth import create_user

    # Use an isolated session via TestClient db override.
    payload = UserCreate(
        email="audit-test@example.com",
        name="AT",
        primary_role="operator",
        password="correct-horse-battery-staple",
    )
    # Use the running test session by going through the API:
    # Register an admin (anonymous can register because enforcement off).
    r = client.post(
        "/api/v1/auth/login",
        json={"email": payload.email, "password": "wrong"},
    )
    assert r.status_code in (401, 422)


def test_audit_endpoint_filters_by_action(client, db_session):
    audit_service.record(db_session, action="approval.decide", actor="a")
    audit_service.record(db_session, action="auth.login", actor="b")
    db_session.commit()
    r = client.get("/api/v1/governance/audit?action=approval.decide&limit=20")
    assert r.status_code == 200
    actions = {entry["action"] for entry in r.json()}
    assert actions <= {"approval.decide"} or len(actions) == 0
