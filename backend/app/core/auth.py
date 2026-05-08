"""Auth dependencies + RBAC helpers.

Sprint 1 — `auth_enforcement_enabled` defaults to False. While off,
`get_current_user` returns a synthetic anonymous operator (id=0, role='anonymous')
so existing routes continue to work without tokens. When on, routes that depend
on `get_current_user` raise 401 without a valid bearer token.

`require_role(...)` is a dependency factory: routes can use it to gate access.
While enforcement is off, role checks always pass (so we can wire role gates
without breaking dev workflows).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User


ANONYMOUS_USER_ID = 0
ANONYMOUS_ROLE = "anonymous"


@dataclass
class CurrentUser:
    """Lightweight bearer for the request principal.

    Routes never receive the SQLAlchemy User instance — they receive this
    dataclass, which is uniform whether enforcement is on or off (anonymous).
    """

    id: int
    email: str
    name: Optional[str]
    primary_role: str
    is_anonymous: bool

    def has_role(self, role: str) -> bool:
        if self.is_anonymous:
            # When enforcement is off, callers should also check the
            # enforcement flag — but treat anonymous as having every role for
            # dev convenience. require_role() handles this explicitly.
            return True
        return self.primary_role == role


_ANONYMOUS = CurrentUser(
    id=ANONYMOUS_USER_ID,
    email="anonymous@bifrost.local",
    name="Anonymous Operator",
    primary_role=ANONYMOUS_ROLE,
    is_anonymous=True,
)


def _extract_bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> CurrentUser:
    settings = get_settings()
    token = _extract_bearer(request)

    if token is None:
        if settings.auth_enforcement_enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return _ANONYMOUS

    payload = decode_access_token(token)
    if payload is None:
        if settings.auth_enforcement_enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return _ANONYMOUS

    sub = payload.get("sub")
    if not sub:
        return _ANONYMOUS
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return _ANONYMOUS

    user = db.scalars(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    ).first()
    if user is None:
        if settings.auth_enforcement_enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return _ANONYMOUS

    return CurrentUser(
        id=user.id,
        email=user.email,
        name=user.name,
        primary_role=user.primary_role,
        is_anonymous=False,
    )


def require_role(*roles: str):
    """Dependency factory — raises 403 if the user lacks any of the roles.

    When enforcement is off, this is a no-op (returns the user). Roles are
    matched against `primary_role`; multi-role checks (via UserRole table)
    arrive in Sprint 2.
    """

    allowed = {r for r in roles if r}

    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        settings = get_settings()
        if not settings.auth_enforcement_enabled:
            return user
        if user.is_anonymous:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if allowed and user.primary_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(sorted(allowed))}",
            )
        return user

    return _check
