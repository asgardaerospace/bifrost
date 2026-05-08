"""Agent coordination — explicit, bounded handoffs.

Doctrine: NO unrestricted multi-agent swarms. NO recursive collaboration.
Coordination happens ONLY through declared handoff edges that map a
predecessor agent's run-result to a successor's bounded trigger.

Sprint 6 wires three explicit handoffs:

    intelligence_agent (supplier_risk cluster detected)
        ↓  emits handoff event
    supplier_risk_agent (mitigation proposals)
        ↓  emits handoff event
    executive_briefing_agent (brief refresh)

No agent invokes another agent directly. The orchestrator decides whether
to enqueue a successor based on a handoff's emit predicate. All handoffs
are logged as operational events with `topic="agents"`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models.autonomy import AutonomyOperation
from app.schemas.operational_event import OperationalEventCreate
from app.services import events as events_service
from app.services.agents import get as get_agent
from app.services.workflow_orchestrator import WorkflowResult, run_agent

logger = logging.getLogger(__name__)


@dataclass
class Handoff:
    name: str
    predecessor: str
    successor: str
    # Predicate decides if the handoff fires. Receives the predecessor's
    # WorkflowResult; returns the trigger string for the successor or None.
    predicate: Callable[[WorkflowResult], Optional[str]]


def _supplier_risk_detected(result: WorkflowResult) -> Optional[str]:
    op = result.operation
    payload = op.payload or {}
    outputs = payload.get("outputs", {})
    clusters = outputs.get("supplier_clusters") or {}
    if clusters:
        return f"intelligence_agent flagged {len(clusters)} supplier_risk cluster(s)"
    return None


def _mitigation_staged(result: WorkflowResult) -> Optional[str]:
    op = result.operation
    payload = op.payload or {}
    outputs = payload.get("outputs", {})
    if (outputs.get("proposed") or 0) > 0:
        return f"supplier_risk_agent staged {outputs['proposed']} mitigation proposal(s)"
    return None


HANDOFFS: tuple[Handoff, ...] = (
    Handoff(
        name="intel→supplier_risk",
        predecessor="intelligence_agent",
        successor="supplier_risk_agent",
        predicate=_supplier_risk_detected,
    ),
    Handoff(
        name="supplier_risk→executive_briefing",
        predecessor="supplier_risk_agent",
        successor="executive_briefing_agent",
        predicate=_mitigation_staged,
    ),
)


def fire_handoffs(
    db: Session, predecessor_name: str, predecessor_result: WorkflowResult
) -> list[WorkflowResult]:
    """Run any handoffs whose predecessor matches and whose predicate fires.

    Bounded propagation: each handoff runs at most one successor. Successors
    do NOT recursively chain through their own handoffs in this Sprint —
    chained coordination requires explicit operator opt-in.
    """
    fired: list[WorkflowResult] = []
    for h in HANDOFFS:
        if h.predecessor != predecessor_name:
            continue
        trigger = h.predicate(predecessor_result)
        if trigger is None:
            continue
        successor = get_agent(h.successor)
        if successor is None:
            logger.warning("handoff %s skipped: successor '%s' not registered", h.name, h.successor)
            continue
        # Audit event before firing.
        events_service.publish(
            db,
            OperationalEventCreate(
                topic="agents",
                event_type="agent.handoff",
                actor=predecessor_name,
                payload={
                    "handoff": h.name,
                    "from": predecessor_name,
                    "to": h.successor,
                    "trigger": trigger,
                    "predecessor_operation_id": predecessor_result.operation.id,
                },
            ),
        )
        result = run_agent(
            db,
            successor,
            trigger=f"handoff:{h.name}",
            mission_id=predecessor_result.operation.mission_id,
            actor=f"handoff:{predecessor_name}",
        )
        fired.append(result)
    return fired
