"""HTTP endpoints for Intelligence OS."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.intel import (
    IntelActionRead,
    IntelByCategory,
    IntelByRegion,
    IntelCategoryBucket,
    IntelIngestionReport,
    IntelItemRead,
    IntelRegionBucket,
    IntelTopSignals,
)
from app.services import intel as intel_service

router = APIRouter()


def _serialize(item) -> IntelItemRead:
    return IntelItemRead.model_validate(item)


# --- list + detail -----------------------------------------------------------


@router.get("/intel", response_model=list[IntelItemRead])
def list_intel(
    category: Optional[str] = None,
    region: Optional[str] = None,
    tag: Optional[str] = None,
    min_score: Optional[int] = Query(None, ge=0, le=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[IntelItemRead]:
    rows = intel_service.list_intel_items(
        db,
        category=category,
        region=region,
        tag=tag,
        min_score=min_score,
        skip=skip,
        limit=limit,
    )
    return [_serialize(r) for r in rows]


@router.get("/intel/top-signals", response_model=IntelTopSignals)
def intel_top_signals(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> IntelTopSignals:
    rows = intel_service.top_signals(db, limit=limit)
    return IntelTopSignals(
        generated_at=datetime.now(timezone.utc),
        total=len(rows),
        items=[_serialize(r) for r in rows],
    )


@router.get("/intel/by-category", response_model=IntelByCategory)
def intel_by_category(
    limit_per_category: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> IntelByCategory:
    grouped = intel_service.group_by_category(
        db, limit_per_category=limit_per_category
    )
    buckets = [
        IntelCategoryBucket(
            category=cat,  # type: ignore[arg-type]
            count=len(items),
            items=[_serialize(i) for i in items],
        )
        for cat, items in sorted(grouped.items())
    ]
    total = sum(b.count for b in buckets)
    return IntelByCategory(
        generated_at=datetime.now(timezone.utc),
        total=total,
        categories=buckets,
    )


@router.get("/intel/by-region", response_model=IntelByRegion)
def intel_by_region(
    limit_per_region: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> IntelByRegion:
    grouped = intel_service.group_by_region(
        db, limit_per_region=limit_per_region
    )
    buckets = [
        IntelRegionBucket(
            region=region,
            count=len(items),
            items=[_serialize(i) for i in items],
        )
        for region, items in sorted(grouped.items())
    ]
    total = sum(b.count for b in buckets)
    return IntelByRegion(
        generated_at=datetime.now(timezone.utc),
        total=total,
        regions=buckets,
    )


@router.get("/intel/summary", response_model=dict)
def intel_summary(db: Session = Depends(get_db)) -> dict:
    return intel_service.counts_summary(db)


@router.get("/intel/{intel_id}", response_model=IntelItemRead)
def get_intel(intel_id: int, db: Session = Depends(get_db)) -> IntelItemRead:
    return _serialize(intel_service.get_intel_item(db, intel_id))


# --- ingestion --------------------------------------------------------------


@router.post(
    "/intel/ingest",
    response_model=IntelIngestionReport,
    status_code=status.HTTP_200_OK,
)
def trigger_ingest(
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> IntelIngestionReport:
    return intel_service.ingest_from_providers(db, actor=actor)


# --- action mutation --------------------------------------------------------


@router.post(
    "/intel/actions/{action_id}/acknowledge", response_model=IntelActionRead
)
def acknowledge_action(
    action_id: int,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> IntelActionRead:
    action = intel_service.update_action_status(
        db, action_id, "acknowledged", actor=actor
    )
    return IntelActionRead.model_validate(action)


@router.post(
    "/intel/actions/{action_id}/resolve", response_model=IntelActionRead
)
def resolve_action(
    action_id: int,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> IntelActionRead:
    action = intel_service.update_action_status(
        db, action_id, "resolved", actor=actor
    )
    return IntelActionRead.model_validate(action)


@router.post(
    "/intel/actions/{action_id}/dismiss", response_model=IntelActionRead
)
def dismiss_action(
    action_id: int,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> IntelActionRead:
    action = intel_service.update_action_status(
        db, action_id, "dismissed", actor=actor
    )
    return IntelActionRead.model_validate(action)
