"""Idempotency + workflow deduplication.

Two layers:

1. In-process registry (app.core.reliability.idempotency) — fast hits within
   a single worker; small TTL.

2. DB-backed registry — persisted via the operational_events table using a
   reserved event_type='idempotency.key' so we don't have to add a new table.
   Lookup by `entity_type='idempotency'`, `entity_id=hash(key)` is O(log n)
   given the existing index on (entity_type, entity_id).

The combined effect: when the same logical action is requested twice (same
key inside the TTL window, even from different workers), the second caller
gets the first caller's result rather than executing again. This keeps
workflow execution deterministic in the face of retries, dropped responses,
and double-clicks.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.observability import metrics
from app.core.reliability import idempotency as in_proc
from app.models.operational_event import OperationalEvent
from app.schemas.operational_event import OperationalEventCreate
from app.services import events as events_service

logger = logging.getLogger("bifrost.idempotency")

IDEMPOTENCY_TOPIC = "events"
IDEMPOTENCY_EVENT_TYPE = "idempotency.key"
IDEMPOTENCY_ENTITY_TYPE = "idempotency"


def _hash(key: str) -> int:
    # Stable 63-bit positive int from the key — fits in BigInt.
    h = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") & ((1 << 63) - 1)


def remember(db: Session, key: str, result: Any) -> None:
    """Record an idempotency result. Persists to DB and to the in-process cache."""
    in_proc.remember(key, result)
    try:
        events_service.publish(
            db,
            OperationalEventCreate(
                topic=IDEMPOTENCY_TOPIC,
                event_type=IDEMPOTENCY_EVENT_TYPE,
                entity_type=IDEMPOTENCY_ENTITY_TYPE,
                entity_id=_hash(key),
                actor="system",
                source="idempotency",
                severity="info",
                payload={"key": key, "result": _safe_result(result)},
            ),
        )
    except Exception:  # pragma: no cover -- defensive
        logger.exception("failed to persist idempotency key=%s", key)


def fetch(db: Session, key: str) -> tuple[bool, Any]:
    """Fetch a previously-recorded idempotent result.

    Hits the in-proc cache first; falls through to a DB lookup so cross-worker
    duplicates are still caught.
    """
    hit, val = in_proc.fetch(key)
    if hit:
        return True, val
    try:
        row = db.scalars(
            select(OperationalEvent).where(
                and_(
                    OperationalEvent.entity_type == IDEMPOTENCY_ENTITY_TYPE,
                    OperationalEvent.entity_id == _hash(key),
                )
            ).order_by(OperationalEvent.id.desc()).limit(1)
        ).first()
    except Exception:
        return False, None
    if row is None:
        return False, None
    payload = row.payload or {}
    if payload.get("key") != key:
        # hash collision (extremely rare); treat as miss.
        return False, None
    metrics.incr("reliability.idempotency.db_hit")
    result = payload.get("result")
    in_proc.remember(key, result)
    return True, result


def _safe_result(result: Any) -> Any:
    try:
        json.dumps(result)
        return result
    except (TypeError, ValueError):
        return repr(result)
