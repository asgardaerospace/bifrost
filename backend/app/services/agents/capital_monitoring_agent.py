"""CapitalMonitoringAgent — flags capital movement signals affecting missions.

Bounded scope:
  - reads:    intel_items (signal_type=funding), signal_relevance
  - proposes: stage_capital_followup
  - approves: human required
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.intel import IntelItem
from app.models.signal import SignalRelevance
from app.services.agents import register
from app.services.agents.base import (
    BaseAgent,
    StageContext,
    StageResult,
)
from app.services.signals import derive_signal_type


class CapitalMonitoringAgent(BaseAgent):
    name = "capital_monitoring_agent"
    version = "0.1.0"
    purpose = (
        "Detects funding-type intelligence with mission-level relevance "
        "and stages capital follow-up proposals."
    )
    allowed_actions = ("stage_capital_followup",)
    required_approvals = ("stage_capital_followup",)
    accessible_domains = ("intel_item", "signal_relevance")
    confidence_threshold = 50
    workflow_key = "capital.monitor"

    def _pipeline(self):
        return [scan_funding_signals, propose_followups]


def scan_funding_signals(ctx: StageContext) -> StageResult:
    db = ctx.db
    rows = db.scalars(
        select(SignalRelevance).where(SignalRelevance.is_relevant.is_(True))
    ).all()
    funding: list[dict] = []
    for r in rows:
        item = db.get(IntelItem, r.intel_item_id)
        if item is None:
            continue
        if derive_signal_type(item) != "funding":
            continue
        funding.append(
            {
                "intel_item_id": item.id,
                "title": item.title,
                "mission_id": r.mission_id,
                "decayed_score": r.decayed_score,
            }
        )
    ctx.outputs["funding_signals"] = funding
    return StageResult(
        output_payload={"count": len(funding)},
        confidence=70 if funding else 25,
    )


def propose_followups(ctx: StageContext) -> StageResult:
    items = ctx.outputs.get("funding_signals", [])
    if not items:
        return StageResult(output_payload={"proposed": 0}, confidence=25)
    from app.services.agents import get as get_agent

    ag = get_agent(ctx.operation.agent_name)
    if ag is None:
        return StageResult(output_payload={}, confidence=0)
    proposed = 0
    for s in items:
        ag.stage_action(
            ctx,
            action_type="stage_capital_followup",
            target_entity_type="mission",
            target_entity_id=s["mission_id"],
            payload={
                "mission_id": s["mission_id"],
                "intel_item_id": s["intel_item_id"],
                "title": s["title"],
                "decayed_score": s["decayed_score"],
                "rationale": (
                    f"Funding signal '{s['title']}' is relevant to mission "
                    f"#{s['mission_id']} (rel {s['decayed_score']}). "
                    "Recommend operator follow-up with the named investor / fund."
                ),
            },
            requires_approval=True,
        )
        proposed += 1
    ctx.outputs["reasoning"] = (
        f"Staged {proposed} capital follow-up proposal(s) from funding-type signals."
    )
    return StageResult(
        output_payload={"proposed": proposed},
        confidence=75 if proposed else 25,
    )


register(CapitalMonitoringAgent())
