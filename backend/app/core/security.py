"""Password hashing + JWT encode/decode."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# bcrypt rejects secrets >72 bytes. Truncate at the boundary in both directions
# so a long passphrase doesn't crash. This is a deliberate, explicit policy.
def _truncate_for_bcrypt(plain: str) -> str:
    encoded = plain.encode("utf-8")
    if len(encoded) <= 72:
        return plain
    return encoded[:72].decode("utf-8", errors="ignore")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(_truncate_for_bcrypt(plain))


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_ctx.verify(_truncate_for_bcrypt(plain), hashed)
    except Exception:
        return False


def create_access_token(
    *,
    subject: str,
    extra_claims: Optional[dict[str, Any]] = None,
    expires_minutes: Optional[int] = None,
) -> str:
    settings = get_settings()
    minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    settings = get_settings()
    try:
        return jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
