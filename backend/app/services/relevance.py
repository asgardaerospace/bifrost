"""Operational relevance engine.

Determines what matters, to whom, for which missions, at what urgency, and
for how long. Sprint 4 is the single most important system in this sprint —
everything else (propagation, executive synthesis, pressure integration)
reads from the persisted SignalRelevance index.

Scoring is deterministic, weighted, and explainable. Each dimension lives
on its own row in the components dict so the operator can audit any score.

Inputs:
  - mission linkage (intel_item.mission_id == mission.id) — strongest signal
  - entity overlap (intel_entities ∩ mission_entities)
  - supplier overlap (intel mentions supplier linked to mission)
  - strategic keyword overlap (mission desc / signal text)
  - regional alignment
  - mission priority weight
  - signal severity / strategic_relevance_score / urgency

Outputs: SignalRelevance row(s) and an updated computed_at + decayed_score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intel import IntelEntity, IntelItem
from app.models.mission import Mission, MissionEntity
from app.models.signal import SignalRelevance
from app.services import signals as signal_helpers


# -- weights (each capped, total clipped to 100) ------------------------------

W_DIRECT_MISSION_LINK = 45  # IntelItem.mission_id == mission.id
W_ENTITY_OVERLAP_PER = 8
W_ENTITY_OVERLAP_CAP = 25
W_SUPPLIER_OVERLAP_PER = 10
W_SUPPLIER_OVERLAP_CAP = 20
W_KEYWORD_OVERLAP = 18  # multiplied by jaccard 0..1
W_REGION_MATCH = 5
W_PRIORITY = {
    "critical": 10,
    "high": 6,
    "normal": 0,
    "low": -3,
}
W_SEVERITY = {
    "critical": 12,
    "warning": 6,
    "notice": 2,
    "info": 0,
}
W_STRATEGIC_RELEVANCE = 0.15  # multiplied by item.strategic_relevance_score (0..100)

RELEVANCE_THRESHOLD = 25  # below this, signal is suppressed for the mission


@dataclass
class RelevanceResult:
    intel_item_id: int
    mission_id: int
    score: int  # 0..100
    decayed_score: int
    components: dict[str, Any]
    is_relevant: bool


def _clip(score: float) -> int:
    return max(0, min(100, int(round(score))))


def _entity_overlap(
    db: Session, *, item: IntelItem, mission: Mission
) -> tuple[int, list[str]]:
    """Count of (entity_type, entity_id) intel entities that map onto a
    MissionEntity link. Returns (count, list of human-readable hits)."""
    intel_entities = db.scalars(
        select(IntelEntity).where(IntelEntity.intel_item_id == item.id)
    ).all()
    if not intel_entities:
        return 0, []
    mission_links = db.scalars(
        select(MissionEntity).where(MissionEntity.mission_id == mission.id)
    ).all()
    by_pair = {
        (m.entity_type, m.entity_id) for m in mission_links if m.entity_id is not None
    }
    hits: list[str] = []
    for ent in intel_entities:
        if ent.entity_id is None:
            continue
        if (ent.entity_type, ent.entity_id) in by_pair:
            hits.append(f"{ent.entity_type}#{ent.entity_id}")
    # Suppliers count for the supplier-overlap term separately when applicable.
    return len(hits), hits


def _supplier_overlap(
    db: Session, *, item: IntelItem, mission: Mission
) -> tuple[int, list[str]]:
    """Mission-linked suppliers mentioned in the signal's IntelEntity rows."""
    intel_entities = db.scalars(
        select(IntelEntity).where(IntelEntity.intel_item_id == item.id)
    ).all()
    mission_supplier_ids: set[int] = {
        m.entity_id
        for m in db.scalars(
            select(MissionEntity).where(
                MissionEntity.mission_id == mission.id,
                MissionEntity.entity_type.in_(("supplier", "program_supplier")),
            )
        ).all()
        if m.entity_id is not None
    }
    if not intel_entities or not mission_supplier_ids:
        return 0, []
    hits: list[str] = []
    for ent in intel_entities:
        if ent.entity_type in ("supplier", "company") and ent.entity_id in mission_supplier_ids:
            hits.append(f"supplier#{ent.entity_id}")
    return len(hits), hits


def _mission_text(mission: Mission) -> str:
    parts = [
        mission.codename or "",
        mission.name or "",
        mission.description or "",
        mission.mission_type or "",
    ]
    return " ".join(p for p in parts if p)


def _signal_text(item: IntelItem) -> str:
    return f"{item.title or ''} {item.summary or ''}"


def compute(
    db: Session, *, item: IntelItem, mission: Mission
) -> RelevanceResult:
    """Score one (signal, mission) pair. Side-effect free."""
    components: dict[str, Any] = {}

    direct = (
        W_DIRECT_MISSION_LINK
        if item.mission_id is not None and item.mission_id == mission.id
        else 0
    )
    components["direct_mission_link"] = direct

    ent_count, ent_hits = _entity_overlap(db, item=item, mission=mission)
    ent_pts = min(W_ENTITY_OVERLAP_CAP, ent_count * W_ENTITY_OVERLAP_PER)
    components["entity_overlap"] = ent_pts
    if ent_hits:
        components["entity_hits"] = ent_hits

    sup_count, sup_hits = _supplier_overlap(db, item=item, mission=mission)
    sup_pts = min(W_SUPPLIER_OVERLAP_CAP, sup_count * W_SUPPLIER_OVERLAP_PER)
    components["supplier_overlap"] = sup_pts
    if sup_hits:
        components["supplier_hits"] = sup_hits

    kw_overlap = signal_helpers.keyword_overlap(
        signal_helpers.tokens(_mission_text(mission)),
        signal_helpers.tokens(_signal_text(item)),
    )
    kw_pts = int(round(W_KEYWORD_OVERLAP * kw_overlap))
    components["keyword_overlap"] = kw_pts

    region_pts = 0
    if (item.region or "").strip().lower():
        # Mission has no first-class region; we infer from linked accounts in
        # later sprints. For now, region_match is informational unless the
        # mission_type happens to mention the region — cheap pass.
        if (item.region or "").lower() in (mission.description or "").lower():
            region_pts = W_REGION_MATCH
    components["region_match"] = region_pts

    pri_pts = W_PRIORITY.get(mission.priority, 0)
    components["mission_priority"] = pri_pts

    sev = signal_helpers.derive_severity(item)
    sev_pts = W_SEVERITY.get(sev, 0)
    components["severity"] = sev_pts
    components["severity_band"] = sev

    strat_pts = int(round(W_STRATEGIC_RELEVANCE * (item.strategic_relevance_score or 0)))
    components["strategic_relevance"] = strat_pts

    raw = (
        direct
        + ent_pts
        + sup_pts
        + kw_pts
        + region_pts
        + pri_pts
        + sev_pts
        + strat_pts
    )
    score = _clip(raw)
    decay = signal_helpers.decay_factor(item.published_at or item.created_at)
    components["decay_factor"] = round(decay, 3)
    decayed = _clip(score * decay)

    return RelevanceResult(
        intel_item_id=item.id,
        mission_id=mission.id,
        score=score,
        decayed_score=decayed,
        components=components,
        is_relevant=decayed >= RELEVANCE_THRESHOLD,
    )


def upsert(db: Session, result: RelevanceResult) -> SignalRelevance:
    """Idempotent persistence keyed on (intel_item_id, mission_id)."""
    existing = db.scalars(
        select(SignalRelevance).where(
            SignalRelevance.intel_item_id == result.intel_item_id,
            SignalRelevance.mission_id == result.mission_id,
        )
    ).first()
    now = datetime.now(timezone.utc)
    if existing is None:
        row = SignalRelevance(
            intel_item_id=result.intel_item_id,
            mission_id=result.mission_id,
            score=result.score,
            decayed_score=result.decayed_score,
            components=result.components,
            is_relevant=result.is_relevant,
            computed_at=now,
        )
        db.add(row)
        db.flush()
        return row
    existing.score = result.score
    existing.decayed_score = result.decayed_score
    existing.components = result.components
    existing.is_relevant = result.is_relevant
    existing.computed_at = now
    db.flush()
    return existing


def score_signal_against_active_missions(
    db: Session, item: IntelItem
) -> list[SignalRelevance]:
    """Score a signal against every active mission and persist relevance rows."""
    missions = db.scalars(
        select(Mission)
        .where(Mission.deleted_at.is_(None))
        .where(Mission.status.in_(("active", "planning")))
    ).all()
    rows: list[SignalRelevance] = []
    for m in missions:
        result = compute(db, item=item, mission=m)
        rows.append(upsert(db, result))
    return rows


def list_relevant_for_mission(
    db: Session,
    mission_id: int,
    *,
    limit: int = 25,
    min_score: int = RELEVANCE_THRESHOLD,
) -> list[tuple[SignalRelevance, IntelItem]]:
    """Return the most-relevant signals for a mission, with the source item."""
    rows = db.scalars(
        select(SignalRelevance)
        .where(SignalRelevance.mission_id == mission_id)
        .where(SignalRelevance.decayed_score >= min_score)
        .order_by(SignalRelevance.decayed_score.desc())
        .limit(limit)
    ).all()
    if not rows:
        return []
    item_ids = [r.intel_item_id for r in rows]
    items = {
        i.id: i
        for i in db.scalars(
            select(IntelItem).where(IntelItem.id.in_(item_ids))
        ).all()
    }
    return [(r, items[r.intel_item_id]) for r in rows if r.intel_item_id in items]
