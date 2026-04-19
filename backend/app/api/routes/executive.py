"""HTTP endpoints for Executive OS."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.executive import ActionQueue, AlertBundle, DailyBriefing
from app.services import executive as exec_service

router = APIRouter()


@router.get("/executive/briefing", response_model=DailyBriefing)
def get_briefing(db: Session = Depends(get_db)) -> DailyBriefing:
    return exec_service.build_briefing(db)


@router.get("/executive/action-queue", response_model=ActionQueue)
def get_action_queue(
    limit: int = Query(50, ge=1, le=500),
    domain: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> ActionQueue:
    queue = exec_service.build_action_queue(db, limit=500)
    items = queue.items
    if domain:
        items = [i for i in items if i.domain == domain]
    counts: dict[str, int] = {}
    for i in items:
        counts[i.domain] = counts.get(i.domain, 0) + 1
    return ActionQueue(
        generated_at=queue.generated_at,
        total=len(items),
        counts_by_domain=counts,
        items=items[:limit],
    )


@router.get("/executive/alerts", response_model=AlertBundle)
def get_alerts(
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> AlertBundle:
    bundle = exec_service.build_alerts(db)
    alerts = bundle.alerts
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    counts: dict[str, int] = {}
    for a in alerts:
        counts[a.severity] = counts.get(a.severity, 0) + 1
    return AlertBundle(
        generated_at=bundle.generated_at,
        total=len(alerts),
        counts_by_severity=counts,
        alerts=alerts,
    )
