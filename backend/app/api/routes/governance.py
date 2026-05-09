"""Governance HTTP surface — execution policy registry + audit trail.

Endpoints:
  GET  /api/v1/governance/policies                   list registered policies
  GET  /api/v1/governance/policies/{action_type}     fetch one
  GET  /api/v1/governance/audit                      recent audit entries
  POST /api/v1/governance/policies/{at}/override     record a manual override

Reads are open by default (mirrors other read surfaces). Override is gated
by the `policy.override` permission so that flipping enforcement on later
also flips enforcement here automatically.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.permissions import P_POLICY_OVERRIDE, require_permission
from app.models.operational_event import OperationalEvent
from app.services import policy as policy_service

router = APIRouter()


class PolicyRead(BaseModel):
    action_type: str
    requires_approval: bool
    min_confidence: float
    max_per_mission_per_hour: int
    escalation_role: str
    description: str


class OverrideRequest(BaseModel):
    reason: str = Field(min_length=4, max_length=512)
    mission_id: Optional[int] = None


class AuditEntry(BaseModel):
    id: int
    action: str
    actor: Optional[str]
    outcome: str
    mission_id: Optional[int]
    target_type: Optional[str]
    target_id: Optional[int]
    severity: str
    occurred_at: str
    detail: Optional[dict] = None


@router.get("/governance/policies", response_model=list[PolicyRead])
def list_policies() -> list[PolicyRead]:
    return [
        PolicyRead(
            action_type=p.action_type,
            requires_approval=p.requires_approval,
            min_confidence=p.min_confidence,
            max_per_mission_per_hour=p.max_per_mission_per_hour,
            escalation_role=p.escalation_role,
            description=p.description,
        )
        for p in policy_service.list_policies()
    ]


@router.get("/governance/policies/{action_type}", response_model=PolicyRead)
def get_policy(action_type: str) -> PolicyRead:
    p = policy_service.get(action_type)
    if p is None:
        raise HTTPException(status_code=404, detail="policy not found")
    return PolicyRead(
        action_type=p.action_type,
        requires_approval=p.requires_approval,
        min_confidence=p.min_confidence,
        max_per_mission_per_hour=p.max_per_mission_per_hour,
        escalation_role=p.escalation_role,
        description=p.description,
    )


@router.post("/governance/policies/{action_type}/override", status_code=204)
def override_policy(
    action_type: str,
    payload: OverrideRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_permission(P_POLICY_OVERRIDE)),
) -> None:
    if policy_service.get(action_type) is None:
        raise HTTPException(status_code=404, detail="policy not found")
    policy_service.override(
        db,
        action_type=action_type,
        mission_id=payload.mission_id,
        actor=user.email,
        reason=payload.reason,
    )
    db.commit()


@router.get("/governance/audit", response_model=list[AuditEntry])
def audit_entries(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    action: Optional[str] = None,
    mission_id: Optional[int] = None,
) -> list[AuditEntry]:
    """Read audit-topic events (descending). Supports filter by action + mission."""
    stmt = select(OperationalEvent).where(OperationalEvent.topic == "audit")
    if mission_id is not None:
        stmt = stmt.where(OperationalEvent.mission_id == mission_id)
    if action:
        stmt = stmt.where(OperationalEvent.event_type == f"audit.{action}")
    stmt = stmt.order_by(OperationalEvent.id.desc()).limit(limit)
    rows = list(db.scalars(stmt).all())
    return [
        AuditEntry(
            id=r.id,
            action=(r.event_type or "audit.unknown").removeprefix("audit."),
            actor=r.actor,
            outcome=(r.payload or {}).get("outcome", "ok") if r.payload else "ok",
            mission_id=r.mission_id,
            target_type=r.entity_type,
            target_id=r.entity_id,
            severity=r.severity or "notice",
            occurred_at=r.created_at.isoformat() if r.created_at else "",
            detail=(r.payload or {}).get("detail") if r.payload else None,
        )
        for r in rows
    ]
