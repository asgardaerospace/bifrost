"""IntelligenceAgent — scans intelligence signals + flags supplier instability.

Bounded scope:
  - reads:    intel_items, signal_relevance, signal_impact
  - proposes: stage_supplier_risk_alert, stage_executive_brief_update
  - approves: human required for any downstream action

Pipeline:
  1. retrieve high-relevance recent intelligence
  2. detect supplier_risk clusters affecting active missions
  3. propose alerts (one per affected mission)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.models.intel import IntelItem
from app.models.signal import SignalImpact, SignalRelevance
from app.services.agents import register
from app.services.agents.base import (
    BaseAgent,
    StageContext,
    StageResult,
)


class IntelligenceAgent(BaseAgent):
    name = "intelligence_agent"
    version = "0.1.0"
    purpose = (
        "Scans recent intelligence signals + propagation impacts. Stages "
        "alerts when supplier_risk signals raise pressure on active missions, "
        "and signals the executive_briefing_agent for downstream synthesis."
    )
    allowed_actions = (
        "stage_supplier_risk_alert",
        "stage_executive_brief_update",
    )
    required_approvals = (
        "stage_supplier_risk_alert",
        "stage_executive_brief_update",
    )
    accessible_domains = ("intel_item", "signal_impact", "mission")
    confidence_threshold = 60
    workflow_key = "intelligence.scan"

    def _pipeline(self):
        return [scan_recent_signals, detect_supplier_clusters, propose_alerts]


def scan_recent_signals(ctx: StageContext) -> StageResult:
    db = ctx.db
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    rows = db.scalars(
        select(SignalRelevance)
        .where(SignalRelevance.is_relevant.is_(True))
        .where(SignalRelevance.computed_at >= cutoff)
        .order_by(SignalRelevance.decayed_score.desc())
        .limit(50)
    ).all()
    ctx.outputs["recent_relevant_count"] = len(rows)
    ctx.outputs["recent_signal_ids"] = [r.intel_item_id for r in rows]
    return StageResult(
        output_payload={"count": len(rows), "lookback_hours": 72},
        confidence=80 if rows else 30,
    )


def detect_supplier_clusters(ctx: StageContext) -> StageResult:
    db = ctx.db
    intel_ids = ctx.outputs.get("recent_signal_ids", [])
    if not intel_ids:
        return StageResult(output_payload={"clusters": []}, confidence=20)

    # Filter to supplier_risk impacts.
    impacts = db.scalars(
        select(SignalImpact)
        .where(SignalImpact.intel_item_id.in_(intel_ids))
        .where(SignalImpact.impact_type == "raises_pressure")
    ).all()
    clusters: dict[int, list[dict[str, Any]]] = {}
    for imp in impacts:
        comps = imp.components if isinstance(imp.components, dict) else {}
        if comps.get("signal_type") != "supplier_risk":
            continue
        item = db.get(IntelItem, imp.intel_item_id)
        if item is None:
            continue
        clusters.setdefault(imp.mission_id, []).append(
            {
                "intel_item_id": imp.intel_item_id,
                "title": item.title,
                "contribution": imp.contribution,
            }
        )
    ctx.outputs["supplier_clusters"] = clusters
    return StageResult(
        output_payload={
            "cluster_count": len(clusters),
            "missions": list(clusters.keys()),
        },
        confidence=85 if clusters else 30,
    )


def propose_alerts(ctx: StageContext) -> StageResult:
    clusters: dict[int, list[dict[str, Any]]] = ctx.outputs.get(
        "supplier_clusters", {}
    )
    proposed = 0
    for mission_id, items in clusters.items():
        # Stage one alert per mission.
        agent = ctx.operation.agent_name  # for symmetry
        from app.services.agents import get as get_agent

        ag = get_agent(agent)
        if ag is None:
            continue
        ag.stage_action(
            ctx,
            action_type="stage_supplier_risk_alert",
            target_entity_type="mission",
            target_entity_id=mission_id,
            payload={
                "mission_id": mission_id,
                "supplier_signal_count": len(items),
                "top_signals": items[:3],
                "rationale": (
                    f"{len(items)} supplier_risk signal(s) raising pressure "
                    f"on mission #{mission_id}; recommend executive review "
                    "and contingency supplier identification."
                ),
            },
            requires_approval=True,
        )
        proposed += 1
    ctx.outputs["alerts_proposed"] = proposed
    ctx.outputs["reasoning"] = (
        f"Detected {proposed} supplier-risk cluster(s) above relevance "
        "threshold. Each alert is approval-gated; no autonomous downstream "
        "action."
    )
    return StageResult(
        output_payload={"alerts_proposed": proposed},
        confidence=85 if proposed else 30,
    )


register(IntelligenceAgent())
