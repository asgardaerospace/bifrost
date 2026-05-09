"""Sprint 8 — JWT hardening (iss/aud/nbf claims, expired handling)."""

from __future__ import annotations

import time

from jose import jwt

from app.core.config import get_settings
from app.core.security import (
    JWT_AUDIENCE,
    JWT_ISSUER,
    create_access_token,
    decode_access_token,
)


def test_token_carries_iss_aud_nbf():
    tok = create_access_token(subject="42")
    settings = get_settings()
    decoded = jwt.decode(
        tok,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
    )
    assert decoded["iss"] == JWT_ISSUER
    assert decoded["aud"] == JWT_AUDIENCE
    assert "nbf" in decoded
    assert "exp" in decoded


def test_decode_rejects_wrong_audience():
    settings = get_settings()
    bad = jwt.encode(
        {
            "sub": "1",
            "iss": JWT_ISSUER,
            "aud": "not-bifrost",
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(bad) is None


def test_decode_rejects_wrong_issuer():
    settings = get_settings()
    bad = jwt.encode(
        {
            "sub": "1",
            "iss": "rogue",
            "aud": JWT_AUDIENCE,
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(bad) is None


def test_decode_rejects_expired():
    settings = get_settings()
    bad = jwt.encode(
        {
            "sub": "1",
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": int(time.time()) - 200,
            "exp": int(time.time()) - 100,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(bad) is None


def test_extra_claims_cannot_override_structural():
    tok = create_access_token(
        subject="42",
        extra_claims={"sub": "999", "iss": "rogue", "role": "operator"},
    )
    decoded = decode_access_token(tok)
    assert decoded is not None
    assert decoded["sub"] == "42"
    assert decoded["iss"] == JWT_ISSUER
    assert decoded["role"] == "operator"
