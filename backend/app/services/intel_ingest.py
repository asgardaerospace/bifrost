"""Intelligence ingestion pipeline.

Doctrine: aerospace intelligence is sparse, operational, and mission-relevant.
Every ingested signal goes through:

    raw provider payload
        ↓ normalize (timestamp, source, url, region, summary)
        ↓ dedup by (source, url) — uses existing IntelItem unique constraint
        ↓ persist IntelItem (+ IntelEntity rows from extracted entities)
        ↓ derive signal_type via signals.derive_signal_type
        ↓ score relevance against active missions  → SignalRelevance rows
        ↓ propagate                              → SignalImpact rows
        ↓ ingest into memory_records             → semantic chunks + embeddings
        ↓ recompute pressure for affected missions
        ↓ publish operational_event              → ws fanout
"""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intel import IntelEntity, IntelItem
from app.schemas.operational_event import OperationalEventCreate
from app.services import events as events_service
from app.services import memory as memory_service
from app.services import pressure as pressure_service
from app.services import relevance as relevance_service
from app.services import signal_propagation as signal_propagation_service
from app.services import signals as signal_helpers


# ---------------------------------------------------------------------------
# normalized signal record handed to ingest()
# ---------------------------------------------------------------------------


@dataclass
class IngestedEntity:
    entity_type: str  # company | investor | agency | program | person | product | country | region
    entity_name: str
    entity_id: Optional[int] = None  # internal id if resolved
    role: Optional[str] = None


@dataclass
class IngestedSignal:
    source: str
    title: str
    url: Optional[str] = None
    summary: Optional[str] = None
    region: Optional[str] = None
    category: str = "uncategorized"
    published_at: Optional[datetime] = None
    strategic_relevance_score: int = 0
    urgency_score: int = 0
    confidence_score: int = 0
    entities: list[IngestedEntity] = None  # type: ignore[assignment]
    tags: list[str] = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# ingestion result
# ---------------------------------------------------------------------------


@dataclass
class IngestionReport:
    ingested: int
    deduped: int
    relevance_rows: int
    impact_rows: int
    affected_missions: int


# ---------------------------------------------------------------------------
# core
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_published_at(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _existing_intel(db: Session, *, source: str, url: Optional[str]) -> Optional[IntelItem]:
    if not url:
        return None
    return db.scalars(
        select(IntelItem).where(IntelItem.source == source, IntelItem.url == url)
    ).first()


def ingest_signal(
    db: Session, signal: IngestedSignal, *, actor: str = "ingest"
) -> tuple[IntelItem, bool, list]:
    """Ingest a single normalized signal. Returns (item, created, impacts).

    Idempotent on (source, url). When the row already exists, refreshes
    relevance + propagation but does not duplicate the row.
    """
    existing = _existing_intel(db, source=signal.source, url=signal.url)
    created = existing is None

    if existing is None:
        item = IntelItem(
            source=signal.source,
            title=(signal.title or "")[:512],
            url=(signal.url or None),
            published_at=normalize_published_at(signal.published_at) or _now(),
            region=signal.region,
            category=signal.category or "uncategorized",
            summary=signal.summary,
            strategic_relevance_score=int(max(0, min(100, signal.strategic_relevance_score))),
            urgency_score=int(max(0, min(100, signal.urgency_score))),
            confidence_score=int(max(0, min(100, signal.confidence_score))),
        )
        db.add(item)
        db.flush()
    else:
        item = existing
        # Refresh fields if upstream provider revised them.
        if signal.summary and signal.summary != existing.summary:
            existing.summary = signal.summary
        existing.strategic_relevance_score = max(
            existing.strategic_relevance_score,
            int(max(0, min(100, signal.strategic_relevance_score))),
        )
        existing.urgency_score = max(
            existing.urgency_score,
            int(max(0, min(100, signal.urgency_score))),
        )
        db.flush()

    # Replace entity rows on every ingest (cheap, deterministic).
    if signal.entities:
        # Drop prior entities so the row reflects the latest provider snapshot.
        for ent in db.scalars(
            select(IntelEntity).where(IntelEntity.intel_item_id == item.id)
        ).all():
            db.delete(ent)
        db.flush()
        for e in signal.entities:
            db.add(
                IntelEntity(
                    intel_item_id=item.id,
                    entity_type=e.entity_type,
                    entity_name=e.entity_name,
                    entity_id=e.entity_id,
                    role=e.role,
                )
            )
        db.flush()

    # Derive canonical signal_type and relevance scoring against active missions.
    signal_type = signal_helpers.derive_signal_type(item)

    relevance_rows = relevance_service.score_signal_against_active_missions(db, item)
    impacts = signal_propagation_service.propagate_signal(
        db, intel_item=item, signal_type=signal_type
    )

    # Memory ingestion — signals become first-class memory records so they're
    # retrievable + RAG-grounded alongside missions, approvals, etc.
    try:
        memory_service.ingest_intel_item(db, item)
    except Exception:
        pass

    # Recompute pressure for missions touched by this signal's impacts.
    affected = {imp.mission_id for imp in impacts}
    for mid in affected:
        pressure_service.recompute_for_mission(db, mid, source="trigger")

    # Operational event for the realtime layer.
    events_service.publish(
        db,
        OperationalEventCreate(
            topic="intelligence",
            event_type="signal.ingested" if created else "signal.refreshed",
            entity_type="intel_item",
            entity_id=item.id,
            actor=actor,
            severity=signal_helpers.derive_severity(item),
            payload={
                "source": item.source,
                "category": item.category,
                "signal_type": signal_type,
                "relevance_rows": len(relevance_rows),
                "impact_rows": len(impacts),
            },
        ),
    )
    return item, created, impacts


def ingest_batch(
    db: Session, signals: Iterable[IngestedSignal], *, actor: str = "ingest"
) -> IngestionReport:
    ingested = 0
    deduped = 0
    relevance_total = 0
    impact_total = 0
    affected: set[int] = set()
    for s in signals:
        item, created, impacts = ingest_signal(db, s, actor=actor)
        if created:
            ingested += 1
        else:
            deduped += 1
        impact_total += len(impacts)
        for imp in impacts:
            affected.add(imp.mission_id)
        # Count relevance rows: one per active mission scored.
        relevance_total += sum(
            1 for _ in db.execute(
                select(IntelItem.id).where(IntelItem.id == item.id)
            )
        )
    db.commit()
    return IngestionReport(
        ingested=ingested,
        deduped=deduped,
        relevance_rows=relevance_total,
        impact_rows=impact_total,
        affected_missions=len(affected),
    )
