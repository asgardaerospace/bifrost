"""Production governance — execution policy registry + enforcement.

Doctrine (AUTONOMY_GOVERNANCE):
  * Every autonomous proposal must be attributable to an agent + operation +
    workflow trace.
  * Every workflow must be observable, replayable, and bounded.
  * Operators must be able to set hard ceilings without redeploying code.

This module exposes:
  * `EXECUTION_POLICIES` — a registry keyed by action_type / workflow_key.
  * `evaluate(...)` — decides whether a proposed action may execute now and
    returns a structured PolicyDecision.
  * Decisions are recorded as audit events and emit operational events on
    the `governance` topic so the shell can show enforcement in realtime.
  * Counters (`policy.allow.*`, `policy.deny.*`) feed observability.

All checks are conservative — when in doubt, escalate (require approval).
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.observability import metrics
from app.schemas.operational_event import OperationalEventCreate
from app.services import audit as audit_service
from app.services import events as events_service

logger = logging.getLogger("bifrost.policy")


# ---------------------------------------------------------------------------
# Policy specifications.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionPolicy:
    """Execution policy for a single action_type or workflow_key.

    Fields:
      action_type:           the symbolic verb this policy gates
      requires_approval:     if True, operation may not execute without an
                             approved Approval row (already enforced today;
                             policy makes it explicit and auditable).
      min_confidence:        floor (0..1). Below this, the proposal is parked
                             and a human review is required.
      max_per_mission_per_h: rate ceiling. 0 = unlimited.
      escalation_role:       role that owns out-of-band escalation.
      description:           human description shown in the policy registry UI.
    """

    action_type: str
    requires_approval: bool = True
    min_confidence: float = 0.5
    max_per_mission_per_hour: int = 0
    escalation_role: str = "executive"
    description: str = ""


# Built-in catalog. Add to this list to introduce a new action class.
EXECUTION_POLICIES: dict[str, ExecutionPolicy] = {
    "queue_item_complete": ExecutionPolicy(
        action_type="queue_item_complete",
        requires_approval=True,
        min_confidence=0.0,
        max_per_mission_per_hour=0,
        description="Mark an execution queue item complete (approval-required path).",
    ),
    "agent_recommend_action": ExecutionPolicy(
        action_type="agent_recommend_action",
        requires_approval=True,
        min_confidence=0.45,
        max_per_mission_per_hour=20,
        description="Agent-proposed action — requires human approval before execute.",
    ),
    "agent_autonomous_observe": ExecutionPolicy(
        action_type="agent_autonomous_observe",
        requires_approval=False,
        min_confidence=0.0,
        max_per_mission_per_hour=0,
        description="Read-only agent observation — no approval needed.",
    ),
    "agent_autonomous_synthesize": ExecutionPolicy(
        action_type="agent_autonomous_synthesize",
        requires_approval=False,
        min_confidence=0.4,
        max_per_mission_per_hour=120,
        description="Agent synthesis output (cards, briefs, summaries).",
    ),
    "communication_send": ExecutionPolicy(
        action_type="communication_send",
        requires_approval=True,
        min_confidence=0.6,
        max_per_mission_per_hour=10,
        escalation_role="executive",
        description="Outbound communication — always approval-required.",
    ),
    "policy_override": ExecutionPolicy(
        action_type="policy_override",
        requires_approval=True,
        min_confidence=0.0,
        max_per_mission_per_hour=5,
        escalation_role="admin",
        description="Manual override of an execution policy — admin only.",
    ),
}


# ---------------------------------------------------------------------------
# Decision result.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyDecision:
    allow: bool
    requires_approval: bool
    reason: str
    policy: ExecutionPolicy
    confidence: float


# ---------------------------------------------------------------------------
# Rate-window registry — bounded, in-memory, per (mission, action).
# ---------------------------------------------------------------------------


class _RateWindow:
    def __init__(self) -> None:
        self._lock = RLock()
        self._buckets: dict[str, deque] = {}

    def hit(self, key: str, *, ceiling: int, window_s: int = 3600) -> bool:
        if ceiling <= 0:
            return True
        now = datetime.now(timezone.utc).timestamp()
        with self._lock:
            buf = self._buckets.setdefault(key, deque())
            cutoff = now - window_s
            while buf and buf[0] < cutoff:
                buf.popleft()
            if len(buf) >= ceiling:
                return False
            buf.append(now)
            return True


_rate = _RateWindow()


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


def get(action_type: str) -> Optional[ExecutionPolicy]:
    return EXECUTION_POLICIES.get(action_type)


def list_policies() -> list[ExecutionPolicy]:
    return list(EXECUTION_POLICIES.values())


def evaluate(
    db: Session,
    *,
    action_type: str,
    confidence: float,
    mission_id: Optional[int],
    actor: str,
    detail: Optional[dict] = None,
) -> PolicyDecision:
    """Decide whether a proposed action may proceed.

    Always emits an audit row + governance event. Caller still controls what
    happens on a deny — typically: escalate to a human, drop the proposal,
    or downgrade to an observe-only action.
    """
    settings = get_settings()
    pol = EXECUTION_POLICIES.get(action_type)
    if pol is None:
        # Unknown actions are conservative: deny + escalate.
        decision = PolicyDecision(
            allow=False,
            requires_approval=True,
            reason="unknown_action_type",
            policy=ExecutionPolicy(action_type=action_type, requires_approval=True),
            confidence=confidence,
        )
        _record(db, decision, mission_id=mission_id, actor=actor, detail=detail)
        return decision

    floor = max(pol.min_confidence, settings.governance_autonomy_confidence_floor)

    if confidence < floor:
        decision = PolicyDecision(
            allow=False,
            requires_approval=True,
            reason="below_confidence_floor",
            policy=pol,
            confidence=confidence,
        )
        _record(db, decision, mission_id=mission_id, actor=actor, detail=detail)
        return decision

    ceiling = (
        pol.max_per_mission_per_hour
        if pol.max_per_mission_per_hour > 0
        else settings.governance_max_proposals_per_mission_per_hour
    )
    rate_key = f"{action_type}::{mission_id or 0}"
    if not _rate.hit(rate_key, ceiling=ceiling):
        decision = PolicyDecision(
            allow=False,
            requires_approval=True,
            reason="rate_ceiling_exceeded",
            policy=pol,
            confidence=confidence,
        )
        _record(db, decision, mission_id=mission_id, actor=actor, detail=detail)
        return decision

    decision = PolicyDecision(
        allow=True,
        requires_approval=pol.requires_approval,
        reason="ok",
        policy=pol,
        confidence=confidence,
    )
    _record(db, decision, mission_id=mission_id, actor=actor, detail=detail)
    return decision


def _record(
    db: Session,
    decision: PolicyDecision,
    *,
    mission_id: Optional[int],
    actor: str,
    detail: Optional[dict],
) -> None:
    label = "allow" if decision.allow else "deny"
    metrics.incr(f"policy.{label}.{decision.policy.action_type}")
    payload = {
        "action_type": decision.policy.action_type,
        "outcome": label,
        "reason": decision.reason,
        "confidence": round(decision.confidence, 3),
        "min_confidence": decision.policy.min_confidence,
        "requires_approval": decision.policy.requires_approval,
        "rate_ceiling": decision.policy.max_per_mission_per_hour,
        "detail": detail or {},
    }
    try:
        events_service.publish(
            db,
            OperationalEventCreate(
                topic="governance",
                event_type=f"policy.{label}",
                mission_id=mission_id,
                entity_type="policy_decision",
                actor=actor,
                source="policy",
                severity="notice" if decision.allow else "warning",
                payload=payload,
            ),
        )
    except Exception:  # pragma: no cover -- defensive
        logger.exception("failed to publish policy event")
    audit_service.record(
        db,
        action=audit_service.ACTION_POLICY_VIOLATION if not decision.allow else audit_service.ACTION_AGENT_RUN,
        actor=actor,
        outcome=label,
        mission_id=mission_id,
        target_type="policy",
        detail=payload,
        severity="warning" if not decision.allow else "notice",
    )


def override(
    db: Session,
    *,
    action_type: str,
    mission_id: Optional[int],
    actor: str,
    reason: str,
) -> None:
    """Record a manual policy override. The act of overriding is itself audited."""
    audit_service.record(
        db,
        action=audit_service.ACTION_POLICY_OVERRIDE,
        actor=actor,
        outcome="ok",
        mission_id=mission_id,
        target_type="policy",
        detail={"action_type": action_type, "reason": reason},
        severity="warning",
    )
    metrics.incr(f"policy.override.{action_type}")
