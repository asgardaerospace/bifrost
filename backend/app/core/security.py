"""Password hashing + JWT encode/decode.

Sprint 8 hardening:
  * iss/aud/nbf claims are now stamped on issuance and validated on decode.
  * Production refuses placeholder secrets and very-short keys.
  * Decoder distinguishes expired vs malformed tokens (both still return None
    to callers — but log_token_failure() emits a structured breadcrumb).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

logger = logging.getLogger("bifrost.security")
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_ISSUER = "bifrost"
JWT_AUDIENCE = "bifrost-operators"


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
    if settings.is_production:
        # Last-line guard — validate_env catches this at boot, but a misconfigured
        # test setup could still slip through into a live process.
        if len(settings.jwt_secret_key) < 32 or settings.jwt_secret_key in {
            "change-me", "smoke-test-secret"
        }:
            raise RuntimeError("JWT_SECRET_KEY is not production-safe")
    minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    if extra_claims:
        # Don't allow extra_claims to override structural ones — defensive.
        for k, v in extra_claims.items():
            if k in {"sub", "iss", "aud", "exp", "nbf", "iat"}:
                continue
            payload[k] = v
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
    except ExpiredSignatureError:
        logger.info("token rejected: expired")
        return None
    except JWTError as exc:
        logger.info("token rejected: %s", exc.__class__.__name__)
        return None
