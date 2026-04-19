"""Translate investor engine payloads into Bifrost-shaped records.

The mapper is the *only* place in the codebase that knows both the
engine shape and the Bifrost shape. Everything upstream sees
`EngineInvestor`, everything downstream sees `NormalizedInvestor`.

Design:
  - Pure functions (no DB, no I/O), trivially unit-testable.
  - Field names align with Bifrost's `InvestorOpportunityRead` /
    `InvestorFirmRead` vocabulary so UI code can treat engine-sourced
    investors uniformly with native ones.
  - Unknown / missing fields degrade to None rather than raising,
    because engine payloads evolve and read-only views should stay up.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel

from app.integrations.investor_engine.schemas import (
    EngineActivity,
    EngineContact,
    EngineInvestor,
)


# ---------------------------------------------------------------------------
# Normalized read model (what Bifrost code consumes)
# ---------------------------------------------------------------------------


class NormalizedContact(BaseModel):
    external_id: str
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    notes: Optional[str] = None


class NormalizedActivity(BaseModel):
    external_id: str
    kind: str
    summary: Optional[str] = None
    occurred_at: Optional[datetime] = None
    author: Optional[str] = None


class NormalizedInvestor(BaseModel):
    """Flattened investor record as Bifrost wants to render it."""

    external_id: str
    source: str = "investor_engine"

    firm_name: str
    website: Optional[str] = None
    stage_focus: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

    stage: Optional[str] = None
    follow_up_status: Optional[str] = None
    last_touch_at: Optional[datetime] = None
    next_follow_up_at: Optional[datetime] = None
    next_step: Optional[str] = None
    owner: Optional[str] = None

    amount: Optional[Decimal] = None
    target_close_date: Optional[date] = None
    fit_score: Optional[int] = None
    probability_score: Optional[int] = None
    strategic_value_score: Optional[int] = None

    contacts: List[NormalizedContact] = []
    recent_activity: List[NormalizedActivity] = []

    engine_updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Stage + status normalization
# ---------------------------------------------------------------------------

# Engine stages are free-form strings; Bifrost has a canonical set.
# Anything unknown passes through untouched — safer than silently
# dropping data the UI might still want to display.
_STAGE_ALIASES = {
    "new": "prospect",
    "lead": "prospect",
    "intro": "prospect",
    "first_meeting": "engaged",
    "engaged": "engaged",
    "diligence": "diligence",
    "dd": "diligence",
    "term_sheet": "term_sheet",
    "closed_won": "closed_won",
    "won": "closed_won",
    "closed_lost": "closed_lost",
    "lost": "closed_lost",
    "pass": "closed_lost",
}

_FOLLOW_UP_ALIASES = {
    "due": "due",
    "overdue": "overdue",
    "scheduled": "scheduled",
    "none": "none",
    "waiting": "waiting",
}


def _normalize_stage(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return _STAGE_ALIASES.get(raw.strip().lower(), raw.strip().lower())


def _normalize_follow_up(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return _FOLLOW_UP_ALIASES.get(raw.strip().lower(), raw.strip().lower())


# ---------------------------------------------------------------------------
# Public mapping API
# ---------------------------------------------------------------------------


def map_contact(c: EngineContact) -> NormalizedContact:
    return NormalizedContact(
        external_id=c.external_id,
        name=c.full_name,
        title=c.title,
        email=c.email,
        phone=c.phone,
        linkedin_url=c.linkedin_url,
        notes=c.notes,
    )


def map_activity(a: EngineActivity) -> NormalizedActivity:
    return NormalizedActivity(
        external_id=a.external_id,
        kind=a.kind,
        summary=a.summary,
        occurred_at=a.occurred_at,
        author=a.author,
    )


def map_investor(inv: EngineInvestor) -> NormalizedInvestor:
    activity_sorted = sorted(
        inv.activity,
        key=lambda a: a.occurred_at or datetime.min,
        reverse=True,
    )
    return NormalizedInvestor(
        external_id=inv.external_id,
        firm_name=inv.firm_name,
        website=inv.website,
        stage_focus=inv.stage_focus,
        location=inv.location,
        description=inv.description,
        stage=_normalize_stage(inv.stage),
        follow_up_status=_normalize_follow_up(inv.follow_up_status),
        last_touch_at=inv.last_touch_at,
        next_follow_up_at=inv.next_follow_up_at,
        next_step=inv.next_step,
        owner=inv.owner,
        amount=inv.amount,
        target_close_date=inv.target_close_date,
        fit_score=inv.fit_score,
        probability_score=inv.probability_score,
        strategic_value_score=inv.strategic_value_score,
        contacts=[map_contact(c) for c in inv.contacts],
        recent_activity=[map_activity(a) for a in activity_sorted[:25]],
        engine_updated_at=inv.updated_at,
    )
