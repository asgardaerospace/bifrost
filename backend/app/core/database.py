import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _engine_kwargs() -> dict:
    """Tune the connection pool. SQLite (smoke harness) gets defaults; Postgres
    in production uses a sized pool with bounded recycling so a long-running
    process doesn't accumulate stale connections after a database restart."""
    base: dict = {"pool_pre_ping": True, "future": True}
    if settings.database_url.startswith("sqlite"):
        return base
    base.update(
        pool_size=int(os.environ.get("DB_POOL_SIZE", "10") or "10"),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10") or "10"),
        pool_recycle=int(os.environ.get("DB_POOL_RECYCLE_S", "1800") or "1800"),
        pool_timeout=int(os.environ.get("DB_POOL_TIMEOUT_S", "30") or "30"),
    )
    return base


engine = create_engine(settings.database_url, **_engine_kwargs())

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
