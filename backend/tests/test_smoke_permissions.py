"""Sprint 8 — RBAC permission framework."""

from __future__ import annotations

from app.core.auth import CurrentUser
from app.core.permissions import (
    P_APPROVAL_DECIDE,
    P_POLICY_OVERRIDE,
    P_SYSTEM_VIEW,
    ROLES,
    role_permissions,
    user_has_permission,
)


def test_role_catalog_includes_baseline():
    assert "admin" in ROLES
    assert "executive" in ROLES
    assert "operator" in ROLES
    assert "analyst" in ROLES
    assert "anonymous" in ROLES


def test_admin_has_all_permissions():
    perms = role_permissions("admin")
    assert P_APPROVAL_DECIDE in perms
    assert P_POLICY_OVERRIDE in perms
    assert P_SYSTEM_VIEW in perms


def test_analyst_cannot_override_policy():
    user = CurrentUser(
        id=1, email="a@x.com", name="Analyst",
        primary_role="analyst", is_anonymous=False,
    )
    assert not user_has_permission(user, P_POLICY_OVERRIDE)


def test_executive_can_decide_approvals():
    user = CurrentUser(
        id=1, email="e@x.com", name="Exec",
        primary_role="executive", is_anonymous=False,
    )
    assert user_has_permission(user, P_APPROVAL_DECIDE)


def test_anonymous_has_no_permissions():
    perms = role_permissions("anonymous")
    assert len(perms) == 0
