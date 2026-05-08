"""Canonical signal helpers — type derivation, severity bands, decay.

Doctrine: aerospace intelligence is operational infrastructure. Every helper
here is deterministic and inspectable; nothing depends on a model call.

The canonical SIGNAL_TYPES are the doctrine-fixed kinds an operator should
recognize at a glance. We derive them from the existing IntelItem.category
values (which were sized for human curation) so legacy intel rows light up
under the new system without a destructive schema change.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Iterable

from app.models.intel import IntelItem


SIGNAL_TYPES = (
    "funding",
    "procurement",
    "supplier_risk",
    "manufacturing",
    "launch",
    "geopolitical",
    "regulatory",
    "defense",
    "partnership",
    "acquisition",
    "market_shift",
)

# IntelItem.category → canonical signal_type. Values that don't appear here
# fall through to "market_shift" (catch-all, low specificity).
_CATEGORY_TO_TYPE: dict[str, str] = {
    "vc_funding": "funding",
    "defense_tech": "defense",
    "space_systems": "launch",
    "aerospace_manufacturing": "manufacturing",
    "supply_chain": "supplier_risk",
    "policy_procurement": "procurement",
    "competitor_move": "market_shift",
    "partner_signal": "partnership",
    "supplier_signal": "supplier_risk",
    "uncategorized": "market_shift",
}

# Strategic keywords used by the relevance engine + signal-type override
# heuristics. Keep this small + curated; this is operational vocabulary, not
# generic NLP.
TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "funding": ("series", "raised", "fund iv", "fund v", "led the round", "valuation"),
    "procurement": ("rfp", "rfi", "contract award", "iquila", "sam.gov", "task order"),
    "supplier_risk": ("recall", "shortage", "shutdown", "delay", "delinquent", "bankrupt"),
    "manufacturing": ("foundry", "machining", "additive", "tooling", "yield"),
    "launch": ("launch", "static fire", "orbital", "payload", "deorbit"),
    "geopolitical": ("export control", "itar", "sanction", "tariff", "treaty"),
    "regulatory": ("faa", "ntsb", "noaa", "fcc license", "rulemaking"),
    "defense": ("dod", "air force", "space force", "darpa", "afrl", "afwerx"),
    "partnership": ("teaming", "mou", "joint", "collaboration", "alliance"),
    "acquisition": ("acquires", "merger", "acquired by", "spin-off"),
    "market_shift": ("strategy", "exit", "consolidation"),
}


# Decay model: relevance score loses half its value every HALF_LIFE_DAYS.
# Tunable; aerospace operational rhythms tend to be week-scale.
HALF_LIFE_DAYS = 14.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def derive_signal_type(item: IntelItem) -> str:
    """Pure function: category + keyword heuristics → canonical type.

    Heuristic order:
      1. category mapping (canonical when curators tagged the item)
      2. keyword override (catches mistagged items)
      3. fall through to market_shift
    """
    base = _CATEGORY_TO_TYPE.get(item.category or "uncategorized", "market_shift")
    text = f"{item.title or ''} {item.summary or ''}".lower()
    # Override only if a more specific type than the catch-all matches strongly.
    if base == "market_shift":
        for stype, kws in TYPE_KEYWORDS.items():
            if any(k in text for k in kws):
                return stype
    return base


def derive_severity(item: IntelItem) -> str:
    """Conservative severity band derived from urgency + strategic_relevance."""
    u = int(item.urgency_score or 0)
    s = int(item.strategic_relevance_score or 0)
    high = max(u, s)
    if high >= 80:
        return "critical"
    if high >= 60:
        return "warning"
    if high >= 35:
        return "notice"
    return "info"


def decay_factor(occurred_at: datetime | None, *, half_life_days: float = HALF_LIFE_DAYS) -> float:
    """Multiplicative decay applied to raw relevance scores."""
    if occurred_at is None:
        return 0.5
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (_now() - occurred_at).total_seconds() / 86400.0)
    return 0.5 ** (age_days / half_life_days)


_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(_TOKEN.findall(text.lower()))


def deterministic_external_id(*, source: str, url: str | None, title: str) -> str:
    """Stable id used for cross-ingestion deduplication.

    A signal published by two providers about the same event should collapse
    to one row. We hash (source, url) when url is present (canonical), else
    fall back to (source, normalized_title).
    """
    import hashlib

    key = (source or "").strip().lower()
    if url:
        key += "\x00" + url.strip().lower()
    else:
        key += "\x00" + " ".join((title or "").strip().lower().split())
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def keyword_overlap(a: Iterable[str], b: Iterable[str]) -> float:
    """Jaccard similarity for two token sets — used by the relevance engine."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)
