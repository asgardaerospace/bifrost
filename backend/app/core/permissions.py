"""Permission framework — symbolic permissions, role mappings, decision API.

Doctrine:
  * Permissions are named verbs (e.g. "approval.decide", "queue.execute",
    "agent.run", "policy.override"). Routes ask for permissions, not roles.
  * Roles are the *default* mapping from a user to a set of permissions; the
    runtime can layer additive overrides per user.
  * Every access decision is recorded via the audit trail.
  * While `auth_enforcement_enabled=False`, permission checks pass — but the
    audit trail still records the would-be decision so we can validate role
    coverage before flipping the flag.

This is the additive enforcement framework Sprint 8 promises — it does not
gate any existing routes by default.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

from fastapi import Depends, HTTPException, status

from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.observability import metrics

logger = logging.getLogger("bifrost.permissions")


# ---------------------------------------------------------------------------
# Permission catalog. Centralised so the audit log uses canonical names.
# ---------------------------------------------------------------------------

P_APPROVAL_DECIDE = "approval.decide"
P_QUEUE_EXECUTE = "queue.execute"
P_AGENT_RUN = "agent.run"
P_AGENT_AUTONOMOUS_PROPOSE = "agent.autonomous_propose"
P_POLICY_OVERRIDE = "policy.override"
P_SYSTEM_VIEW = "system.view"
P_USER_MANAGE = "user.manage"
P_DATA_EXPORT = "data.export"

ALL_PERMISSIONS: tuple[str, ...] = (
    P_APPROVAL_DECIDE,
    P_QUEUE_EXECUTE,
    P_AGENT_RUN,
    P_AGENT_AUTONOMOUS_PROPOSE,
    P_POLICY_OVERRIDE,
    P_SYSTEM_VIEW,
    P_USER_MANAGE,
    P_DATA_EXPORT,
)


@dataclass(frozen=True)
class RoleSpec:
    name: str
    permissions: frozenset[str] = field(default_factory=frozenset)
    description: str = ""


# Default role -> permission map. Operators inherit decide+execute on
# missions they are allowed into; admins inherit everything.
ROLES: dict[str, RoleSpec] = {
    "admin": RoleSpec(
        name="admin",
        permissions=frozenset(ALL_PERMISSIONS),
        description="System administrators — full surface.",
    ),
    "executive": RoleSpec(
        name="executive",
        permissions=frozenset({
            P_APPROVAL_DECIDE,
            P_QUEUE_EXECUTE,
            P_AGENT_RUN,
            P_POLICY_OVERRIDE,
            P_SYSTEM_VIEW,
            P_DATA_EXPORT,
        }),
        description="Mission executives — approve, override, view system state.",
    ),
    "operator": RoleSpec(
        name="operator",
        permissions=frozenset({
            P_APPROVAL_DECIDE,
            P_QUEUE_EXECUTE,
            P_AGENT_RUN,
        }),
        description="Operators — execute work, decide on routine approvals.",
    ),
    "analyst": RoleSpec(
        name="analyst",
        permissions=frozenset({
            P_AGENT_RUN,
        }),
        description="Analysts — run agents, read-mostly access.",
    ),
    "anonymous": RoleSpec(
        name="anonymous",
        permissions=frozenset(),
        description="Pre-auth synthetic operator — never has perms once enforcement is on.",
    ),
}


def role_permissions(role: str) -> frozenset[str]:
    spec = ROLES.get(role)
    return spec.permissions if spec else frozenset()


def user_has_permission(user: CurrentUser, permission: str) -> bool:
    return permission in role_permissions(user.primary_role)


# ---------------------------------------------------------------------------
# FastAPI dependency factory.
# ---------------------------------------------------------------------------


def require_permission(*permissions: str):
    """Dependency factory — gate a route on one or more permissions.

    While enforcement is off, denies are downgraded to log-only events so we
    can build coverage without breaking dev workflows. Once enforcement is on,
    a deny becomes a 403.
    """
    needed = tuple(p for p in permissions if p)

    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        settings = get_settings()
        # Determine outcome.
        if user.is_anonymous:
            granted = not settings.auth_enforcement_enabled
        else:
            granted = all(user_has_permission(user, p) for p in needed)

        # Audit + metrics — always.
        outcome = "allow" if granted else "deny"
        metrics.incr(f"permissions.{outcome}.{'+'.join(needed) or '*'}")
        logger.info(
            "permission_check",
            extra={
                "permissions": list(needed),
                "user_id": user.id,
                "role": user.primary_role,
                "outcome": outcome,
                "enforced": settings.auth_enforcement_enabled,
            },
        )

        if granted:
            return user

        if not settings.auth_enforcement_enabled:
            # Shadow mode — let the request through but the audit log records
            # the would-be denial. This is the migration path to enforcement.
            return user

        if user.is_anonymous:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission(s): {', '.join(needed)}",
        )

    return _check


def evaluate(user: CurrentUser, permissions: Iterable[str]) -> bool:
    """Programmatic permission check (no FastAPI dependency)."""
    return all(user_has_permission(user, p) for p in permissions)
