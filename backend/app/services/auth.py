"""AuthService — registration + login.

Dev-mode behavior: when `auth_enforcement_enabled` is False and the looked-up
user has no `password_hash` set, login accepts any (or absent) password. This
unlocks demos and local dev without forcing every user to register a password.
When enforcement is True, a valid password is always required.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserRead


def _to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        status=user.status,
        primary_role=user.primary_role,
        has_password=user.password_hash is not None,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def get_by_email(db: Session, email: str) -> Optional[User]:
    return db.scalars(
        select(User)
        .where(User.email == email.lower())
        .where(User.deleted_at.is_(None))
    ).first()


def create_user(db: Session, payload: UserCreate) -> User:
    email = payload.email.strip().lower()
    if get_by_email(db, email) is not None:
        raise HTTPException(status_code=409, detail=f"User '{email}' already exists")
    user = User(
        email=email,
        name=payload.name,
        primary_role=payload.primary_role,
        password_hash=hash_password(payload.password) if payload.password else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, *, email: str, password: Optional[str]) -> User:
    settings = get_settings()
    user = get_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if user.password_hash is None:
        if settings.auth_enforcement_enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="user has no password set; ask an admin to set one",
            )
        # Dev mode: accept email-only login.
        return user
    if not password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="password required"
        )
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )
    return user


def to_read(user: User) -> UserRead:
    return _to_read(user)
