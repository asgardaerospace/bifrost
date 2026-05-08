"""MissionCoordinationAgent — flags missions whose pressure is rising.

Bounded scope:
  - reads:    missions, mission_pressure_snapshots
  - proposes: stage_mission_coordination_review
  - approves: human required
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.mission import Mission
from app.models.pressure_snapshot import MissionPressureSnapshot
from app.services.agents import register
from app.services.agents.base import (
    BaseAgent,
    StageContext,
    StageResult,
)


class MissionCoordinationAgent(BaseAgent):
    name = "mission_coordination_agent"
    version = "0.1.0"
    purpose = (
        "Detects active missions whose pressure trajectory is rising "
        "and stages a coordination review proposal."
    )
    allowed_actions = ("stage_mission_coordination_review",)
    required_approvals = ("stage_mission_coordination_review",)
    accessible_domains = ("mission", "mission_pressure_snapshot")
    confidence_threshold = 55
    workflow_key = "mission.coordinate"

    def _pipeline(self):
        return [identify_rising_missions, propose_review]


def identify_rising_missions(ctx: StageContext) -> StageResult:
    db = ctx.db
    rising: list[dict] = []
    missions = db.scalars(
        select(Mission)
        .where(Mission.deleted_at.is_(None))
        .where(Mission.status == "active")
    ).all()
    for m in missions:
        snapshots = db.scalars(
            select(MissionPressureSnapshot)
            .where(MissionPressureSnapshot.mission_id == m.id)
            .order_by(MissionPressureSnapshot.computed_at.desc())
            .limit(5)
        ).all()
        if len(snapshots) < 2:
            continue
        latest = snapshots[0].score
        previous = snapshots[-1].score
        delta = latest - previous
        if delta >= 8 and latest >= 35:
            rising.append(
                {
                    "mission_id": m.id,
                    "codename": m.codename,
                    "delta": delta,
                    "latest": latest,
                    "previous": previous,
                }
            )
    ctx.outputs["rising_missions"] = rising
    return StageResult(
        output_payload={"rising_count": len(rising)},
        confidence=80 if rising else 30,
    )


def propose_review(ctx: StageContext) -> StageResult:
    rising = ctx.outputs.get("rising_missions", [])
    if not rising:
        return StageResult(output_payload={"proposed": 0}, confidence=30)
    from app.services.agents import get as get_agent

    ag = get_agent(ctx.operation.agent_name)
    if ag is None:
        return StageResult(output_payload={}, confidence=0)
    proposed = 0
    for r in rising:
        ag.stage_action(
            ctx,
            action_type="stage_mission_coordination_review",
            target_entity_type="mission",
            target_entity_id=r["mission_id"],
            payload={
                "mission_id": r["mission_id"],
                "codename": r["codename"],
                "pressure_delta": r["delta"],
                "latest_pressure": r["latest"],
                "rationale": (
                    f"Mission {r['codename']} pressure rose from "
                    f"{r['previous']} to {r['latest']} (Δ +{r['delta']}). "
                    "Recommend a coordination review of blockers, approvals, "
                    "and recent intelligence."
                ),
            },
            requires_approval=True,
        )
        proposed += 1
    ctx.outputs["reasoning"] = (
        f"Staged {proposed} mission coordination review(s) on rising "
        "pressure trajectories."
    )
    return StageResult(
        output_payload={"proposed": proposed},
        confidence=80 if proposed else 30,
    )


register(MissionCoordinationAgent())
