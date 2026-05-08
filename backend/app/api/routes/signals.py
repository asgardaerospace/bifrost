"""Signal-system HTTP routes (Sprint 4)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.intel import IntelItem
from app.models.signal import SignalImpact, SignalRelevance
from app.schemas.signal import (
    IngestionReportRead,
    IngestionTrigger,
    MissionSignalRead,
    MissionSignalsResponse,
    SignalImpactRead,
    SignalRelevanceRead,
    SignalSummaryRead,
)
from app.services import intel_ingest as ingest_service
from app.services import relevance as relevance_service
from app.services import signal_propagation as signal_propagation_service
from app.services import signals as signal_helpers
from app.services.intel_providers.aerospace_seed import aerospace_seed_signals

router = APIRouter()


def _summary(item: IntelItem) -> SignalSummaryRead:
    return SignalSummaryRead(
        id=item.id,
        source=item.source,
        title=item.title,
        url=item.url,
        region=item.region,
        category=item.category,
        summary=item.summary,
        published_at=item.published_at,
        strategic_relevance_score=item.strategic_relevance_score,
        urgency_score=item.urgency_score,
        confidence_score=item.confidence_score,
        signal_type=signal_helpers.derive_signal_type(item),
        severity=signal_helpers.derive_severity(item),
    )


# -- ingestion ---------------------------------------------------------------


@router.post(
    "/intelligence/ingest",
    response_model=IngestionReportRead,
    status_code=status.HTTP_201_CREATED,
)
def trigger_ingest(
    payload: IngestionTrigger,
    db: Session = Depends(get_db),
) -> IngestionReportRead:
    """Run a curated provider end-to-end. Sprint 4 ships only the
    `aerospace_seed` provider; real RSS / procurement adapters are added by
    operators and registered here in later sprints."""
    if payload.provider == "aerospace_seed":
        signals = aerospace_seed_signals()
    else:
        raise HTTPException(
            status_code=400, detail=f"Unknown provider '{payload.provider}'"
        )
    report = ingest_service.ingest_batch(db, signals, actor=payload.actor)
    return IngestionReportRead(
        ingested=report.ingested,
        deduped=report.deduped,
        relevance_rows=report.relevance_rows,
        impact_rows=report.impact_rows,
        affected_missions=report.affected_missions,
    )


# -- signals -----------------------------------------------------------------


@router.get(
    "/intelligence/signals", response_model=list[SignalSummaryRead]
)
def list_signals(
    signal_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SignalSummaryRead]:
    stmt = select(IntelItem).order_by(IntelItem.published_at.desc()).limit(limit)
    if region:
        stmt = stmt.where(IntelItem.region == region)
    rows = list(db.scalars(stmt).all())
    summaries = [_summary(r) for r in rows]
    if signal_type:
        summaries = [s for s in summaries if s.signal_type == signal_type]
    if severity:
        summaries = [s for s in summaries if s.severity == severity]
    return summaries


@router.get(
    "/intelligence/signals/{signal_id}", response_model=SignalSummaryRead
)
def get_signal(signal_id: int, db: Session = Depends(get_db)) -> SignalSummaryRead:
    item = db.get(IntelItem, signal_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Signal #{signal_id} not found")
    return _summary(item)


@router.get(
    "/intelligence/signals/{signal_id}/relevance",
    response_model=list[SignalRelevanceRead],
)
def signal_relevance(
    signal_id: int, db: Session = Depends(get_db)
) -> list[SignalRelevanceRead]:
    rows = list(
        db.scalars(
            select(SignalRelevance)
            .where(SignalRelevance.intel_item_id == signal_id)
            .order_by(SignalRelevance.decayed_score.desc())
        ).all()
    )
    return [SignalRelevanceRead.model_validate(r) for r in rows]


@router.get(
    "/intelligence/signals/{signal_id}/impacts",
    response_model=list[SignalImpactRead],
)
def signal_impacts(
    signal_id: int, db: Session = Depends(get_db)
) -> list[SignalImpactRead]:
    rows = list(
        db.scalars(
            select(SignalImpact)
            .where(SignalImpact.intel_item_id == signal_id)
            .order_by(SignalImpact.contribution.desc())
        ).all()
    )
    return [SignalImpactRead.model_validate(r) for r in rows]


# -- mission-side surfaces ---------------------------------------------------


@router.get(
    "/missions/{mission_id}/intelligence",
    response_model=MissionSignalsResponse,
)
def mission_intelligence(
    mission_id: int,
    limit: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
) -> MissionSignalsResponse:
    pairs = relevance_service.list_relevant_for_mission(db, mission_id, limit=limit)
    impacts_by_intel = {
        imp.intel_item_id: imp
        for imp in db.scalars(
            select(SignalImpact).where(SignalImpact.mission_id == mission_id)
        ).all()
    }
    items: list[MissionSignalRead] = []
    for rel, item in pairs:
        imp = impacts_by_intel.get(item.id)
        items.append(
            MissionSignalRead(
                relevance=SignalRelevanceRead.model_validate(rel),
                signal=_summary(item),
                impact_type=imp.impact_type if imp else None,
                contribution=imp.contribution if imp else None,
            )
        )
    return MissionSignalsResponse(
        mission_id=mission_id, count=len(items), items=items
    )
