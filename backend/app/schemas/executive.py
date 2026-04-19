"""Executive OS schemas — unified briefing, action queue, and alerts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from app.schemas.base import ORMModel


Domain = Literal["capital", "market", "program", "supplier", "approval", "engine"]
Severity = Literal["info", "warn", "critical"]


# --- action queue ---------------------------------------------------------


class ActionItem(ORMModel):
    id: str  # stable per-source string id, e.g. "program.overdue.42"
    domain: Domain
    kind: str  # finer-grained source tag inside the domain
    title: str
    description: Optional[str] = None
    priority_score: int  # 0..100, deterministic
    due_at: Optional[datetime] = None
    status: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    source_label: str  # "Investor pipeline", "Market follow-ups", ...
    link_hint: Optional[str] = None  # frontend path suggestion


class ActionQueue(ORMModel):
    generated_at: datetime
    total: int
    counts_by_domain: dict[str, int]
    items: list[ActionItem]


# --- alerts ---------------------------------------------------------------


class Alert(ORMModel):
    id: str
    severity: Severity
    domain: Domain
    title: str
    description: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    recommended_action: str
    link_hint: Optional[str] = None


class AlertBundle(ORMModel):
    generated_at: datetime
    total: int
    counts_by_severity: dict[str, int]
    alerts: list[Alert]


# --- daily briefing -------------------------------------------------------


class BriefingItem(ORMModel):
    """Lightweight row used inside briefing sections."""

    label: str
    subtitle: Optional[str] = None
    badge: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    link_hint: Optional[str] = None


class BriefingSection(ORMModel):
    domain: Domain
    title: str
    headline: str
    count: int
    items: list[BriefingItem] = []


class ExecutiveMetrics(ORMModel):
    # Pulled deterministically from domain summaries.
    capital_active: int = 0
    capital_overdue: int = 0
    capital_stale: int = 0
    capital_pending_approvals: int = 0
    market_accounts: int = 0
    market_active_campaigns: int = 0
    market_active_opportunities: int = 0
    market_follow_ups_due: int = 0
    programs_active: int = 0
    programs_high_value: int = 0
    programs_overdue: int = 0
    suppliers_total: int = 0
    suppliers_qualified: int = 0
    suppliers_onboarded: int = 0
    engine_writes_pending: int = 0
    engine_writes_failed: int = 0


class DailyBriefing(ORMModel):
    generated_at: datetime
    headline: str  # one-line operator summary
    narrative: list[str]  # bullet-level narrative strings
    metrics: ExecutiveMetrics
    sections: list[BriefingSection]
    top_actions: list[ActionItem]
    top_risks: list[Alert]
