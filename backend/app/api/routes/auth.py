"""Auth HTTP routes — login, register, current user."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user, require_role
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.user import (
    CurrentUserRead,
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserRead,
)
from app.services import audit as audit_service
from app.services import auth as auth_service

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    try:
        user = auth_service.authenticate(db, email=payload.email, password=payload.password)
    except Exception:
        audit_service.record(
            db,
            action=audit_service.ACTION_AUTH_LOGIN_FAILED,
            actor=payload.email or "anonymous",
            outcome="fail",
            severity="warning",
            detail={"email": payload.email},
        )
        db.commit()
        raise
    token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.primary_role, "email": user.email},
    )
    audit_service.record(
        db,
        action=audit_service.ACTION_AUTH_LOGIN,
        actor=user.email,
        outcome="ok",
        target_type="user",
        target_id=user.id,
    )
    db.commit()
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        user=auth_service.to_read(user),
    )


@router.post(
    "/auth/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    # When enforcement is on, only admins can register users. When off,
    # require_role is a no-op (Sprint 1 — Sprint 2 introduces tighter role
    # enforcement and proper user provisioning flow).
    _user: CurrentUser = Depends(require_role("admin")),
) -> UserRead:
    user = auth_service.create_user(db, payload)
    return auth_service.to_read(user)


@router.get("/auth/me", response_model=CurrentUserRead)
def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUserRead:
    return CurrentUserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        primary_role=user.primary_role,
        is_anonymous=user.is_anonymous,
    )
