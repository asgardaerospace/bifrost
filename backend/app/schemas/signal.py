"""Sprint 4 signal + relevance + executive schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.schemas.base import ORMModel, TimestampedRead


class SignalRelevanceRead(TimestampedRead):
    intel_item_id: int
    mission_id: int
    score: int
    decayed_score: int
    components: dict[str, Any]
    is_relevant: bool
    expires_at: Optional[datetime] = None
    computed_at: datetime


class SignalImpactRead(TimestampedRead):
    intel_item_id: int
    mission_id: int
    impact_type: str
    contribution: int
    components: dict[str, Any]
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None
    computed_at: datetime


class SignalSummaryRead(ORMModel):
    """Compact view of a signal joined with derived fields used by the UI."""

    id: int
    source: str
    title: str
    url: Optional[str] = None
    region: Optional[str] = None
    category: str
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    strategic_relevance_score: int
    urgency_score: int
    confidence_score: int
    signal_type: str
    severity: str


class MissionSignalRead(ORMModel):
    """One row in the mission-detail "linked intelligence" surface."""

    relevance: SignalRelevanceRead
    signal: SignalSummaryRead
    impact_type: Optional[str] = None
    contribution: Optional[int] = None


class MissionSignalsResponse(ORMModel):
    mission_id: int
    count: int
    items: list[MissionSignalRead]


class IngestionTrigger(ORMModel):
    provider: str = "aerospace_seed"
    actor: str = "operator"


class IngestionReportRead(ORMModel):
    ingested: int
    deduped: int
    relevance_rows: int
    impact_rows: int
    affected_missions: int
