"""User schemas (Sprint 1 — auth foundation)."""

from __future__ import annotations

from typing import Optional

from app.schemas.base import ORMModel, TimestampedRead


class UserCreate(ORMModel):
    email: str
    name: Optional[str] = None
    primary_role: str = "operator"
    password: Optional[str] = None  # Optional in dev; required when enforcement on.


class UserRead(TimestampedRead):
    email: str
    name: Optional[str] = None
    status: str
    primary_role: str
    has_password: bool


class UserUpdate(ORMModel):
    name: Optional[str] = None
    primary_role: Optional[str] = None
    status: Optional[str] = None


class LoginRequest(ORMModel):
    email: str
    password: Optional[str] = None  # Optional iff user has no password set and enforcement off.


class TokenResponse(ORMModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserRead


class CurrentUserRead(ORMModel):
    id: int
    email: str
    name: Optional[str] = None
    primary_role: str
    is_anonymous: bool
