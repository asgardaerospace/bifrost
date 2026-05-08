"""SupplierRiskAgent — proposes supplier-risk mitigation actions.

Bounded scope:
  - reads:    signal_impact, mission_entities, suppliers
  - proposes: stage_mitigation_recommendation, stage_freeze_vendor_approvals
  - approves: human required
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.mission import MissionEntity
from app.models.signal import SignalImpact
from app.services.agents import register
from app.services.agents.base import (
    BaseAgent,
    StageContext,
    StageResult,
)


class SupplierRiskAgent(BaseAgent):
    name = "supplier_risk_agent"
    version = "0.1.0"
    purpose = (
        "Translates supplier_risk SignalImpact rows into concrete, "
        "approval-gated mitigation proposals (contingency review, vendor "
        "approval freezes)."
    )
    allowed_actions = (
        "stage_mitigation_recommendation",
        "stage_freeze_vendor_approvals",
    )
    required_approvals = (
        "stage_mitigation_recommendation",
        "stage_freeze_vendor_approvals",
    )
    accessible_domains = ("signal_impact", "mission_entity", "supplier")
    confidence_threshold = 55
    workflow_key = "supplier_risk.mitigate"

    def _pipeline(self):
        return [collect_at_risk, propose_mitigation]


def collect_at_risk(ctx: StageContext) -> StageResult:
    db = ctx.db
    impacts = db.scalars(
        select(SignalImpact).where(SignalImpact.impact_type == "raises_pressure")
    ).all()
    at_risk = [
        imp
        for imp in impacts
        if isinstance(imp.components, dict)
        and imp.components.get("signal_type") == "supplier_risk"
    ]
    ctx.outputs["at_risk_count"] = len(at_risk)
    ctx.outputs["at_risk_impact_ids"] = [imp.id for imp in at_risk]
    return StageResult(
        output_payload={"count": len(at_risk)},
        confidence=80 if at_risk else 25,
    )


def propose_mitigation(ctx: StageContext) -> StageResult:
    db = ctx.db
    impact_ids = ctx.outputs.get("at_risk_impact_ids", [])
    if not impact_ids:
        return StageResult(
            output_payload={"proposed": 0},
            confidence=25,
        )
    impacts = db.scalars(
        select(SignalImpact).where(SignalImpact.id.in_(impact_ids))
    ).all()
    from app.services.agents import get as get_agent

    ag = get_agent(ctx.operation.agent_name)
    if ag is None:
        return StageResult(output_payload={}, confidence=0)

    proposed = 0
    for imp in impacts:
        # Identify suppliers linked to the affected mission.
        linked_suppliers = db.scalars(
            select(MissionEntity).where(
                MissionEntity.mission_id == imp.mission_id,
                MissionEntity.entity_type.in_(("supplier", "program_supplier")),
            )
        ).all()
        ag.stage_action(
            ctx,
            action_type="stage_mitigation_recommendation",
            target_entity_type="mission",
            target_entity_id=imp.mission_id,
            payload={
                "mission_id": imp.mission_id,
                "intel_item_id": imp.intel_item_id,
                "linked_supplier_count": len(linked_suppliers),
                "contribution": imp.contribution,
                "rationale": (
                    f"Supplier_risk signal contributes +{imp.contribution} "
                    f"pressure on mission #{imp.mission_id}; mitigation "
                    "candidates: identify backup vendors, freeze related "
                    "approvals, schedule contingency review."
                ),
            },
            requires_approval=True,
        )
        proposed += 1
    ctx.outputs["proposed"] = proposed
    ctx.outputs["reasoning"] = (
        f"Proposed {proposed} mitigation recommendation(s); each is "
        "approval-gated and reversible (proposed → approved | rejected)."
    )
    return StageResult(
        output_payload={"proposed": proposed},
        confidence=80 if proposed else 25,
    )


register(SupplierRiskAgent())
