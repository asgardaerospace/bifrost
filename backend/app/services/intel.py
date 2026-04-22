"""Intelligence OS service.

Owns ingestion, classification, persistence, and query for external
intel items. Writes are modular and backend-only — the frontend only
reads normalized rows through the /intel endpoints.

Design principles:
  - Ingestion is read-only: we never write back to external providers.
  - Dedupe on (source, url) so re-running ingestion is idempotent.
  - Classification is deterministic (see intel_classifier) so every
    score/tag/action can be explained from code.
  - External intel rows never get a FK to internal tables. We capture
    an entity_type + entity_name with an optional nullable entity_id
    hint instead — see IntelEntity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.intel import (
    IntelAction,
    IntelEntity,
    IntelItem,
    IntelTag,
)
from app.schemas.intel import (
    IntelIngestionReport,
    IntelItemCreate,
)
from app.services import intel_classifier
from app.services.activity import log_activity
from app.services.intel_providers import REGISTRY as PROVIDER_REGISTRY
from app.services.intel_providers.base import IntelProvider

ENTITY_INTEL_ITEM = "intel_item"

# Strategic thresholds (module-level so they're easy to tune/inspect).
TOP_SIGNAL_MIN_SCORE = 50
EXEC_BRIEFING_LIMIT = 5


# ---------------------------------------------------------------------------
# query helpers
# ---------------------------------------------------------------------------


def _not_found(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"{name} not found"
    )


def _base_query():
    return (
        select(IntelItem)
        .options(
            selectinload(IntelItem.entities),
            selectinload(IntelItem.tags),
            selectinload(IntelItem.actions),
        )
    )


def list_intel_items(
    db: Session,
    *,
    category: Optional[str] = None,
    region: Optional[str] = None,
    tag: Optional[str] = None,
    min_score: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[IntelItem]:
    stmt = _base_query()
    if category:
        stmt = stmt.where(IntelItem.category == category)
    if region:
        stmt = stmt.where(IntelItem.region == region)
    if min_score is not None:
        stmt = stmt.where(IntelItem.strategic_relevance_score >= min_score)
    if tag:
        stmt = stmt.join(IntelTag, IntelTag.intel_item_id == IntelItem.id).where(
            IntelTag.tag == tag
        )
    stmt = stmt.order_by(
        desc(IntelItem.strategic_relevance_score),
        desc(IntelItem.urgency_score),
        desc(IntelItem.published_at),
    )
    stmt = stmt.offset(skip).limit(limit)
    return list(db.execute(stmt).unique().scalars().all())


def get_intel_item(db: Session, item_id: int) -> IntelItem:
    stmt = _base_query().where(IntelItem.id == item_id)
    item = db.execute(stmt).unique().scalar_one_or_none()
    if item is None:
        raise _not_found("intel item")
    return item


def top_signals(db: Session, *, limit: int = 10) -> list[IntelItem]:
    stmt = (
        _base_query()
        .where(IntelItem.strategic_relevance_score >= TOP_SIGNAL_MIN_SCORE)
        .order_by(
            desc(IntelItem.strategic_relevance_score),
            desc(IntelItem.urgency_score),
            desc(IntelItem.published_at),
        )
        .limit(limit)
    )
    return list(db.execute(stmt).unique().scalars().all())


def group_by_category(
    db: Session, *, limit_per_category: int = 10
) -> dict[str, list[IntelItem]]:
    rows = list_intel_items(db, limit=500)
    buckets: dict[str, list[IntelItem]] = {}
    for r in rows:
        bucket = buckets.setdefault(r.category, [])
        if len(bucket) < limit_per_category:
            bucket.append(r)
    return buckets


def group_by_region(
    db: Session, *, limit_per_region: int = 10
) -> dict[str, list[IntelItem]]:
    rows = list_intel_items(db, limit=500)
    buckets: dict[str, list[IntelItem]] = {}
    for r in rows:
        key = r.region or "Unknown"
        bucket = buckets.setdefault(key, [])
        if len(bucket) < limit_per_region:
            bucket.append(r)
    return buckets


def counts_summary(db: Session) -> dict[str, int]:
    total = db.execute(
        select(func.count()).select_from(IntelItem)
    ).scalar_one()
    by_category_rows = db.execute(
        select(IntelItem.category, func.count()).group_by(IntelItem.category)
    ).all()
    top = db.execute(
        select(func.count())
        .select_from(IntelItem)
        .where(IntelItem.strategic_relevance_score >= TOP_SIGNAL_MIN_SCORE)
    ).scalar_one()
    out: dict[str, int] = {
        "total": int(total),
        "top_signals": int(top),
    }
    for cat, count in by_category_rows:
        out[f"category.{cat}"] = int(count)
    return out


# ---------------------------------------------------------------------------
# ingestion + classification pipeline
# ---------------------------------------------------------------------------


def _existing_by_source_url(
    db: Session, source: str, url: Optional[str]
) -> Optional[IntelItem]:
    if url is None:
        return None
    stmt = select(IntelItem).where(
        IntelItem.source == source, IntelItem.url == url
    )
    return db.execute(stmt).scalar_one_or_none()


def _apply_classification(
    db: Session, item: IntelItem, payload: IntelItemCreate
) -> None:
    result = intel_classifier.classify(payload)
    item.category = result.category
    item.strategic_relevance_score = result.strategic_relevance
    item.urgency_score = result.urgency
    item.confidence_score = result.confidence
    if result.region and not item.region:
        item.region = result.region

    # Rebuild tags and actions deterministically so re-ingestion cannot
    # fork the classification.
    for t in list(item.tags):
        db.delete(t)
    for a in list(item.actions):
        # Preserve non-pending decisions made by the operator.
        if a.status == "pending":
            db.delete(a)
    db.flush()

    for tag in result.tags:
        item.tags.append(IntelTag(tag=tag))
    for action_type, recommended in result.recommended_actions:
        # Avoid re-adding if an acknowledged copy already exists.
        has_existing = any(
            a.action_type == action_type and a.status != "pending"
            for a in item.actions
        )
        if has_existing:
            continue
        item.actions.append(
            IntelAction(
                action_type=action_type,
                recommended_action=recommended,
                status="pending",
            )
        )


def _persist(
    db: Session, payload: IntelItemCreate, *, actor: Optional[str]
) -> tuple[IntelItem, bool]:
    """Create-or-update by (source, url). Returns (item, was_created)."""
    existing = _existing_by_source_url(db, payload.source, payload.url)
    if existing is not None:
        existing.title = payload.title
        existing.summary = payload.summary
        existing.published_at = payload.published_at or existing.published_at
        existing.region = payload.region or existing.region
        _apply_classification(db, existing, payload)
        db.flush()
        return existing, False

    item = IntelItem(
        source=payload.source,
        title=payload.title,
        url=payload.url,
        published_at=payload.published_at,
        region=payload.region,
        summary=payload.summary,
        category="uncategorized",
    )
    db.add(item)
    db.flush()  # assign id

    # entity hints from the provider
    for hint in payload.raw_entities:
        item.entities.append(
            IntelEntity(
                entity_type=hint.entity_type,
                entity_name=hint.entity_name,
                role=hint.role,
            )
        )
    _apply_classification(db, item, payload)
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_INTEL_ITEM,
        entity_id=item.id,
        event_type="intel.ingested",
        summary=f"Intel ingested from {payload.source}: {payload.title[:120]}",
        actor=actor,
        actor_type="intel_ingestion",
        details={
            "category": item.category,
            "strategic_relevance_score": item.strategic_relevance_score,
            "urgency_score": item.urgency_score,
        },
    )
    return item, True


def ingest_item(
    db: Session, payload: IntelItemCreate, *, actor: Optional[str] = None
) -> IntelItem:
    """Public single-item entry point — primarily for tests/admin use."""
    item, _ = _persist(db, payload, actor=actor)
    db.commit()
    db.refresh(item)
    return item


def ingest_from_providers(
    db: Session,
    *,
    providers: Optional[list[IntelProvider]] = None,
    actor: Optional[str] = None,
) -> IntelIngestionReport:
    """Run all providers and persist classified items.

    Returns a structured report so callers (CLI, cron, API) can render a
    deterministic summary without re-querying the DB.
    """
    use = providers if providers is not None else PROVIDER_REGISTRY
    started = datetime.now(timezone.utc)
    created = 0
    updated = 0
    skipped = 0
    total = 0
    provider_counts: dict[str, int] = {}

    for provider in use:
        count = 0
        for payload in provider.fetch():
            count += 1
            total += 1
            try:
                _, was_created = _persist(db, payload, actor=actor)
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception:  # pragma: no cover — keep ingestion resilient
                db.rollback()
                skipped += 1
                continue
        provider_counts[getattr(provider, "name", provider.__class__.__name__)] = count

    db.commit()
    finished = datetime.now(timezone.utc)
    return IntelIngestionReport(
        started_at=started,
        finished_at=finished,
        provider_counts=provider_counts,
        created=created,
        updated=updated,
        skipped=skipped,
        total_items_seen=total,
    )


# ---------------------------------------------------------------------------
# action mutation
# ---------------------------------------------------------------------------


def update_action_status(
    db: Session, action_id: int, new_status: str, *, actor: Optional[str] = None
) -> IntelAction:
    action = db.get(IntelAction, action_id)
    if action is None:
        raise _not_found("intel action")
    action.status = new_status
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_INTEL_ITEM,
        entity_id=action.intel_item_id,
        event_type=f"intel.action.{new_status}",
        summary=(
            f"Intel action {action.action_type} marked {new_status}."
        ),
        actor=actor,
    )
    db.commit()
    db.refresh(action)
    return action
