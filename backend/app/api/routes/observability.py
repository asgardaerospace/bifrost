"""Observability HTTP surface — readiness probe + metrics + system snapshot.

Endpoints:
  GET /api/v1/health             — liveness (always cheap; existing route)
  GET /api/v1/health/db          — DB reachable (existing route)
  GET /api/v1/health/ready       — full readiness (db + redis + migrations)
  GET /api/v1/observability/metrics  — in-process metrics snapshot
  GET /api/v1/observability/system   — websocket / pubsub / pressure summary

These are intended for operators and automation. Not gated by enforcement
yet; once auth_enforcement_enabled is on, the system endpoint requires the
`admin` role. The metrics endpoint stays open for scrape jobs.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, require_role
from app.core.database import get_db
from app.core.observability import metrics
from app.services.pubsub import manager as pubsub_manager

router = APIRouter()


@router.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Full readiness probe — checks DB, alembic head, and (if configured) Redis."""
    out: dict[str, Any] = {"status": "ok", "checks": {}}
    # DB
    try:
        db.execute(text("SELECT 1"))
        out["checks"]["database"] = "ok"
    except SQLAlchemyError as exc:  # pragma: no cover -- network
        out["status"] = "degraded"
        out["checks"]["database"] = f"fail: {exc.__class__.__name__}"
    # Alembic head present (may be missing in smoke harness — soft check).
    try:
        row = db.execute(text("SELECT version_num FROM alembic_version")).first()
        out["checks"]["alembic"] = row[0] if row else "missing"
    except SQLAlchemyError:
        out["checks"]["alembic"] = "missing"
    # Redis (if configured)
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis  # type: ignore[import-not-found]

            r = redis.from_url(redis_url, socket_timeout=2)
            r.ping()
            out["checks"]["redis"] = "ok"
        except Exception as exc:  # pragma: no cover -- network
            out["status"] = "degraded"
            out["checks"]["redis"] = f"fail: {exc.__class__.__name__}"
    return out


@router.get("/observability/metrics")
def metrics_snapshot() -> dict[str, Any]:
    """In-process metrics snapshot. Counters, gauges, timer histograms."""
    snap = metrics.snapshot()
    snap["pubsub"] = {
        "connections": pubsub_manager.connection_count,
    }
    return snap


@router.get("/observability/system")
def system_snapshot(
    _user: CurrentUser = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Operational snapshot for the awareness surface — connections, breakers,
    recent error counters, governance ceilings."""
    from app.core.config import get_settings

    settings = get_settings()
    snap = metrics.snapshot()
    return {
        "environment": settings.environment,
        "auth_enforcement_enabled": settings.auth_enforcement_enabled,
        "pubsub": {
            "connections": pubsub_manager.connection_count,
            "redis_attached": pubsub_manager._redis is not None,
        },
        "rate_limit": {
            "enabled": settings.rate_limit_enabled,
            "rpm": settings.rate_limit_rpm,
            "burst": settings.rate_limit_burst,
        },
        "governance": {
            "autonomy_confidence_floor": settings.governance_autonomy_confidence_floor,
            "max_proposals_per_mission_per_hour": settings.governance_max_proposals_per_mission_per_hour,
        },
        "counters": snap["counters"],
        "gauges": snap["gauges"],
    }
