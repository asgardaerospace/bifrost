"""Audit trail — append-only log of governance-relevant decisions.

Implementation: thin wrapper around the operational_events table, using a
reserved topic `audit` and well-known event_type names. Routes / services
call `audit.record(...)` whenever something approval-, authority-, or
override-relevant happens.

We don't introduce a new table — operational_events already has the right
shape (mission scoping, actor, payload, timestamp, indexed for replay) and
we want every audit fact to also flow through the realtime ribbon so the
shell can display the trail without a separate fetch.

Doctrine:
  * Append-only — no updates, no deletes from this layer.
  * Every entry carries: actor, action, target, mission_id (when applicable),
    outcome, and the active trace id for cross-system correlation.
  * Failure to write an audit row never blocks the underlying business action;
    the failure itself is logged for triage.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.observability import current_trace, metrics
from app.schemas.operational_event import OperationalEventCreate
from app.services import events as events_service

logger = logging.getLogger("bifrost.audit")

AUDIT_TOPIC = "audit"

# Canonical action verbs.
ACTION_AUTH_LOGIN = "auth.login"
ACTION_AUTH_LOGIN_FAILED = "auth.login_failed"
ACTION_PERMISSION_DENY = "permission.deny"
ACTION_APPROVAL_DECIDE = "approval.decide"
ACTION_QUEUE_EXECUTE = "queue.execute"
ACTION_AGENT_RUN = "agent.run"
ACTION_AGENT_AUTONOMOUS_PROPOSE = "agent.autonomous_propose"
ACTION_POLICY_OVERRIDE = "policy.override"
ACTION_POLICY_VIOLATION = "policy.violation"
ACTION_DATA_EXPORT = "data.export"
ACTION_USER_CREATE = "user.create"


def record(
    db: Session,
    *,
    action: str,
    actor: str,
    outcome: str = "ok",
    mission_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    detail: Optional[dict[str, Any]] = None,
    severity: str = "notice",
) -> None:
    """Append a single audit entry. Best-effort; never raises."""
    payload: dict[str, Any] = {
        "action": action,
        "outcome": outcome,
        "actor": actor,
    }
    trace = current_trace()
    if trace:
        payload["trace"] = {k: v for k, v in trace.items() if k != "mission_id"}
    if detail:
        payload["detail"] = detail

    try:
        events_service.publish(
            db,
            OperationalEventCreate(
                topic=AUDIT_TOPIC,
                event_type=f"audit.{action}",
                mission_id=mission_id,
                entity_type=target_type,
                entity_id=target_id,
                actor=actor,
                source="audit",
                severity=severity,
                payload=payload,
            ),
        )
        metrics.incr(f"audit.{action}.{outcome}")
    except Exception:
        # Audit write failure must never block the business action.
        logger.exception("audit write failed action=%s actor=%s outcome=%s", action, actor, outcome)
