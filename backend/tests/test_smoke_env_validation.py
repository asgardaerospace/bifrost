"""Sprint 8 — environment validation."""

from __future__ import annotations

import os

from app.scripts.validate_env import validate


def test_validate_passes_in_test_env():
    results = validate()
    failed = [r for r in results if not r[1]]
    # In the smoke harness, ENVIRONMENT=test (not prod), so no prod-specific
    # rules apply. Required keys are set in conftest. Should be all green.
    assert not failed, f"unexpected failures: {failed}"


def test_validate_flags_short_secret_in_prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    results = validate()
    failed = [r[0] for r in results if not r[1]]
    assert any("JWT_SECRET_KEY" in n for n in failed)


def test_validate_flags_sqlite_in_prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./bifrost.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 48)
    results = validate()
    failed = [r[0] for r in results if not r[1]]
    assert any("DATABASE_URL" in n for n in failed)


def test_validate_flags_wildcard_cors_in_prod(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 48)
    monkeypatch.setenv("CORS_ORIGINS", "*")
    results = validate()
    failed = [r[0] for r in results if not r[1]]
    assert any("CORS_ORIGINS" in n for n in failed)
