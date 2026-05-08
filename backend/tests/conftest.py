"""Sprint 0 smoke-test fixtures.

Strategy: most tests run against an in-memory SQLite database created via
`Base.metadata.create_all`, with JSONB columns auto-degrading to JSON via a
SQLAlchemy variant override applied at module import time. This lets the smoke
harness run anywhere with no Postgres dependency while still exercising the
real ORM models, routes, and services. Migration files are NOT run in smoke
tests — those are validated against Postgres in CI / dev (see DEVELOPMENT.md).
"""

from __future__ import annotations

import os

# Set env BEFORE importing app modules so app.core.config picks them up.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "smoke-test-secret")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


# Make JSONB compile as JSON on SQLite for the smoke harness only. Production
# keeps native JSONB on Postgres — this only affects DDL compilation when the
# bound dialect is sqlite.
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # type: ignore[no-untyped-def]
    return "JSON"

from app.core.database import get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.base import Base  # noqa: E402
import app.models  # noqa: F401, E402  -- ensure all models register on Base


@pytest.fixture()
def _engine():
    """Per-test engine.

    StaticPool ensures all connections share the same in-memory SQLite DB so
    the TestClient request thread sees the schema created on the test thread.
    Function-scoped so each test starts with a clean DB.
    """
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def db_session(_engine) -> Session:
    SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, autocommit=False, future=True
    )
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture()
def client(_engine) -> TestClient:
    TestSessionLocal = sessionmaker(
        bind=_engine, autoflush=False, autocommit=False, future=True
    )

    def override_get_db():
        s = TestSessionLocal()
        try:
            yield s
        finally:
            s.close()

    # The websocket route + lifespan create raw sessions via
    # app.core.database.SessionLocal (not via the dependency). Rebind that
    # module-level factory to the test engine for the duration of the test.
    import app.core.database as db_module
    import app.api.routes.ws as ws_module

    saved_core = db_module.SessionLocal
    saved_ws = getattr(ws_module, "SessionLocal", None)
    db_module.SessionLocal = TestSessionLocal
    ws_module.SessionLocal = TestSessionLocal

    fastapi_app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        db_module.SessionLocal = saved_core
        if saved_ws is not None:
            ws_module.SessionLocal = saved_ws
