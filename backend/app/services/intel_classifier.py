"""Rule-based intel classifier.

Deterministic keyword matching drives category selection, relevance tags,
and recommended actions. No LLM required. Rules are intentionally coarse —
they exist to make the intel stream structured and auditable; an LLM
enrichment pass can be layered on top later without changing the schema.

Contract:

    classify(item_create) -> ClassificationResult

where ClassificationResult carries:
  - category               (IntelCategory enum value)
  - strategic_relevance    (0..100)
  - urgency                (0..100)
  - confidence             (0..100; reflects rule match strength)
  - tags                   (list of stable tag strings)
  - recommended_actions    (list of (action_type, recommended_action))

Scoring lives here so the operator can inspect and tune weights without
tracing service calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.schemas.intel import IntelItemCreate

# --- category rules ---------------------------------------------------------
#
# Each rule is (category, [keyword-groups]) where a keyword-group is a list
# of lowercase tokens that must all appear in the combined title+summary.
# First matching rule wins. Ordering matters — put the most specific rules
# first.
#

_CategoryRule = tuple[str, list[list[str]]]

CATEGORY_RULES: list[_CategoryRule] = [
    (
        "vc_funding",
        [
            ["series", "round"],
            ["series", "funding"],
            ["seed", "round"],
            ["raised"],
            ["venture", "round"],
            ["led", "by"],
            ["funding"],
            ["term", "sheet"],
        ],
    ),
    (
        "space_systems",
        [
            ["satellite"],
            ["launch", "vehicle"],
            ["spacex"],
            ["rocket"],
            ["orbit"],
            ["space", "force"],
            ["space", "systems"],
            ["geo"],
            ["leo"],
        ],
    ),
    (
        "defense_tech",
        [
            ["dod"],
            ["pentagon"],
            ["defense", "contract"],
            ["defense", "department"],
            ["dio"],
            ["darpa"],
            ["diu"],
            ["defense"],
            ["military"],
            ["hypersonic"],
            ["unmanned"],
            ["autonomous", "weapon"],
            ["counter", "uas"],
        ],
    ),
    (
        "policy_procurement",
        [
            ["itar"],
            ["ear"],
            ["export", "control"],
            ["procurement"],
            ["appropriations"],
            ["federal", "contract"],
            ["rfp"],
            ["rfi"],
            ["gao"],
            ["senate", "committee"],
            ["house", "committee"],
            ["regulation"],
        ],
    ),
    (
        "aerospace_manufacturing",
        [
            ["additive", "manufacturing"],
            ["composites"],
            ["boeing"],
            ["airbus"],
            ["lockheed"],
            ["northrop"],
            ["raytheon"],
            ["aerostructures"],
            ["factory"],
            ["production", "line"],
            ["manufacturing"],
        ],
    ),
    (
        "supply_chain",
        [
            ["supply", "chain"],
            ["shortage"],
            ["tariff"],
            ["export", "ban"],
            ["component", "shortage"],
            ["logistics"],
        ],
    ),
    (
        "competitor_move",
        [
            ["acquires"],
            ["acquisition"],
            ["merger"],
            ["acquired"],
            ["launches", "competitor"],
            ["expands", "into"],
        ],
    ),
    (
        "partner_signal",
        [
            ["partnership"],
            ["teaming", "agreement"],
            ["mou"],
            ["strategic", "partner"],
            ["jv"],
            ["joint", "venture"],
        ],
    ),
    (
        "supplier_signal",
        [
            ["supplier"],
            ["vendor"],
            ["tier", "1"],
            ["tier", "2"],
            ["as9100"],
            ["nadcap"],
        ],
    ),
]


# --- relevance tag rules ---------------------------------------------------
#
# A single item may match multiple relevance tags. Tags are stable strings
# that downstream systems (action queue, executive briefing, command
# console) pattern-match on.
#

INVESTOR_TAG_TERMS = [
    "series a",
    "series b",
    "series c",
    "seed round",
    "led by",
    "raised",
    "venture",
    "vc",
    "fund",
    "term sheet",
]

MARKET_TAG_TERMS = [
    "acquires",
    "acquisition",
    "merger",
    "boeing",
    "airbus",
    "lockheed",
    "northrop",
    "raytheon",
    "spacex",
    "anduril",
    "rtx",
    "l3harris",
    "kratos",
    "shield ai",
    "palantir",
]

PROGRAM_TAG_TERMS = [
    "dod",
    "pentagon",
    "space force",
    "defense contract",
    "rfp",
    "rfi",
    "procurement",
    "appropriations",
    "federal contract",
    "darpa",
    "diu",
]

SUPPLIER_TAG_TERMS = [
    "supplier",
    "vendor",
    "tier 1",
    "tier 2",
    "as9100",
    "nadcap",
    "shortage",
    "tariff",
    "export ban",
    "supply chain",
]

WATCHLIST_TERMS = [
    "spacex",
    "anduril",
    "shield ai",
    "palantir",
    "boeing",
    "airbus",
    "lockheed",
    "northrop",
    "raytheon",
    "rtx",
    "kratos",
    "l3harris",
    "blue origin",
]


# --- region detection ------------------------------------------------------

_REGION_HINTS: list[tuple[str, list[str]]] = [
    ("US", ["united states", " us ", "washington", "pentagon", "dod"]),
    ("Europe", ["europe", " eu ", "germany", "france", "uk", "britain", "italy"]),
    ("Asia-Pacific", ["china", "japan", "korea", "taiwan", "australia", "india"]),
    ("Middle East", ["israel", "uae", "saudi", "qatar"]),
    ("Global", ["global", "worldwide"]),
]


# --- scoring weights -------------------------------------------------------
#
# Strategic relevance: how much does Asgard care.
#   +30 any relevance tag
#   +15 per additional relevance domain (investor/market/program/supplier)
#   +20 watchlist company hit
#   +15 category in {vc_funding, defense_tech, space_systems}
#
# Urgency: how time-sensitive.
#   +40 published within last 48h
#   +25 published within last 7d
#   +15 published within last 30d
#   +15 urgency keyword hit (breaking, urgent, critical, breach, emergency)
#   +15 supplier signal (shortage/tariff/ban) — supply shocks move fast
#
# Confidence: how sure we are the classification is right.
#   +25 category matched by rule (non-default)
#   +10 per relevance tag matched (cap 3)
#   +15 any entity hint present
#   +10 url present
#

URGENCY_TERMS = [
    "breaking",
    "urgent",
    "critical",
    "breach",
    "emergency",
    "halt",
    "cease",
]


@dataclass
class ClassificationResult:
    category: str
    strategic_relevance: int
    urgency: int
    confidence: int
    tags: list[str] = field(default_factory=list)
    recommended_actions: list[tuple[str, str]] = field(default_factory=list)
    region: Optional[str] = None


def _clip(n: float) -> int:
    return max(0, min(100, int(round(n))))


def _blob(item: IntelItemCreate) -> str:
    parts = [item.title or "", item.summary or ""]
    return " ".join(p.strip() for p in parts if p).lower()


def _match_category(blob: str) -> tuple[str, bool]:
    for category, groups in CATEGORY_RULES:
        for group in groups:
            if all(token in blob for token in group):
                return category, True
    return "uncategorized", False


def _match_terms(blob: str, terms: list[str]) -> list[str]:
    return [t for t in terms if t in blob]


def _detect_region(item: IntelItemCreate, blob: str) -> Optional[str]:
    if item.region:
        return item.region
    for region, hints in _REGION_HINTS:
        for hint in hints:
            if hint in blob:
                return region
    return None


def _days_since(published_at: Optional[datetime]) -> Optional[float]:
    if published_at is None:
        return None
    now = datetime.now(timezone.utc)
    pub = (
        published_at
        if published_at.tzinfo is not None
        else published_at.replace(tzinfo=timezone.utc)
    )
    delta = now - pub
    return max(0.0, delta.total_seconds() / 86400.0)


# --- tag / action derivation -----------------------------------------------


_RECOMMENDED_ACTIONS: dict[str, tuple[str, str]] = {
    "investor-relevant": (
        "review_investor",
        "Review investor activity — check pipeline overlap and outreach fit.",
    ),
    "market-relevant": (
        "review_account",
        "Assess market impact — confirm account coverage and competitive position.",
    ),
    "program-relevant": (
        "review_program",
        "Check program exposure — does this shift procurement odds or priorities?",
    ),
    "supplier-relevant": (
        "review_supplier",
        "Validate supplier risk — identify exposure to this supply chain event.",
    ),
    "watchlist": (
        "watchlist",
        "Watchlist hit — keep an eye on follow-up signals from this company.",
    ),
}


def classify(item: IntelItemCreate) -> ClassificationResult:
    blob = _blob(item)
    category, matched = _match_category(blob)

    tags: list[str] = []
    if _match_terms(blob, INVESTOR_TAG_TERMS) or category == "vc_funding":
        tags.append("investor-relevant")
    if _match_terms(blob, MARKET_TAG_TERMS) or category in (
        "competitor_move",
        "partner_signal",
    ):
        tags.append("market-relevant")
    if _match_terms(blob, PROGRAM_TAG_TERMS) or category in (
        "defense_tech",
        "policy_procurement",
        "space_systems",
    ):
        tags.append("program-relevant")
    if _match_terms(blob, SUPPLIER_TAG_TERMS) or category in (
        "supply_chain",
        "supplier_signal",
        "aerospace_manufacturing",
    ):
        tags.append("supplier-relevant")
    if _match_terms(blob, WATCHLIST_TERMS):
        tags.append("watchlist")

    # --- strategic relevance ---
    relevance_domains = {
        t for t in tags if t.endswith("-relevant")
    }
    strategic = 0.0
    if tags:
        strategic += 30
    strategic += 15 * max(0, len(relevance_domains) - 1)
    if "watchlist" in tags:
        strategic += 20
    if category in ("vc_funding", "defense_tech", "space_systems"):
        strategic += 15
    strategic = _clip(strategic)

    # --- urgency ---
    urgency = 0.0
    days = _days_since(item.published_at)
    if days is not None:
        if days <= 2:
            urgency += 40
        elif days <= 7:
            urgency += 25
        elif days <= 30:
            urgency += 15
    if _match_terms(blob, URGENCY_TERMS):
        urgency += 15
    if category in ("supply_chain", "supplier_signal"):
        urgency += 15
    urgency = _clip(urgency)

    # --- confidence ---
    confidence = 0.0
    if matched:
        confidence += 25
    confidence += 10 * min(3, len([t for t in tags if t.endswith("-relevant")]))
    if item.raw_entities:
        confidence += 15
    if item.url:
        confidence += 10
    confidence = _clip(confidence)

    region = _detect_region(item, blob)

    actions: list[tuple[str, str]] = []
    for tag in tags:
        hit = _RECOMMENDED_ACTIONS.get(tag)
        if hit is not None and hit not in actions:
            actions.append(hit)

    return ClassificationResult(
        category=category,
        strategic_relevance=strategic,
        urgency=urgency,
        confidence=confidence,
        tags=tags,
        recommended_actions=actions,
        region=region,
    )
