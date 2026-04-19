from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.investor import InvestorContact, InvestorFirm, InvestorOpportunity
from app.schemas.investor import (
    InvestorContactCreate,
    InvestorContactUpdate,
    InvestorFirmCreate,
    InvestorFirmUpdate,
    InvestorOpportunityCreate,
    InvestorOpportunityUpdate,
)
from app.services.activity import log_activity

ENTITY_FIRM = "investor_firm"
ENTITY_CONTACT = "investor_contact"
ENTITY_OPPORTUNITY = "investor_opportunity"


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for key, new_value in after.items():
        old_value = before.get(key)
        if old_value != new_value:
            changes[key] = {"from": old_value, "to": new_value}
    return changes


def _snapshot(obj: Any, fields: list[str]) -> dict[str, Any]:
    return {f: getattr(obj, f) for f in fields}


# ---------------------------------------------------------------------------
# investor_firms
# ---------------------------------------------------------------------------

FIRM_FIELDS = [
    "name", "website", "stage_focus", "location", "description", "status",
]


def list_firms(
    db: Session, *, skip: int = 0, limit: int = 50, include_deleted: bool = False
) -> list[InvestorFirm]:
    stmt = select(InvestorFirm)
    if not include_deleted:
        stmt = stmt.where(InvestorFirm.deleted_at.is_(None))
    stmt = stmt.order_by(InvestorFirm.id.desc()).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def get_firm(db: Session, firm_id: int, *, include_deleted: bool = False) -> InvestorFirm:
    firm = db.get(InvestorFirm, firm_id)
    if firm is None or (not include_deleted and firm.deleted_at is not None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investor firm not found")
    return firm


def create_firm(
    db: Session, payload: InvestorFirmCreate, *, actor: Optional[str] = None
) -> InvestorFirm:
    firm = InvestorFirm(**payload.model_dump())
    db.add(firm)
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_FIRM,
        entity_id=firm.id,
        event_type="investor_firm.created",
        summary=f"Created investor firm '{firm.name}'",
        actor=actor,
        details={"firm": _snapshot(firm, FIRM_FIELDS)},
    )
    db.commit()
    db.refresh(firm)
    return firm


def update_firm(
    db: Session,
    firm_id: int,
    payload: InvestorFirmUpdate,
    *,
    actor: Optional[str] = None,
) -> InvestorFirm:
    firm = get_firm(db, firm_id)
    before = _snapshot(firm, FIRM_FIELDS)

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(firm, key, value)
    db.flush()

    after = _snapshot(firm, FIRM_FIELDS)
    changes = _diff(before, after)
    log_activity(
        db,
        entity_type=ENTITY_FIRM,
        entity_id=firm.id,
        event_type="investor_firm.updated",
        summary=f"Updated investor firm '{firm.name}'",
        actor=actor,
        details={"changes": changes} if changes else None,
    )
    db.commit()
    db.refresh(firm)
    return firm


def delete_firm(db: Session, firm_id: int, *, actor: Optional[str] = None) -> None:
    firm = get_firm(db, firm_id)
    firm.deleted_at = datetime.now(timezone.utc)
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_FIRM,
        entity_id=firm.id,
        event_type="investor_firm.deleted",
        summary=f"Soft-deleted investor firm '{firm.name}'",
        actor=actor,
    )
    db.commit()


# ---------------------------------------------------------------------------
# investor_contacts
# ---------------------------------------------------------------------------

CONTACT_FIELDS = [
    "firm_id", "name", "title", "email", "phone", "linkedin_url", "notes",
]


def list_contacts(
    db: Session,
    *,
    firm_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    include_deleted: bool = False,
) -> list[InvestorContact]:
    stmt = select(InvestorContact)
    if firm_id is not None:
        stmt = stmt.where(InvestorContact.firm_id == firm_id)
    if not include_deleted:
        stmt = stmt.where(InvestorContact.deleted_at.is_(None))
    stmt = stmt.order_by(InvestorContact.id.desc()).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def get_contact(
    db: Session, contact_id: int, *, include_deleted: bool = False
) -> InvestorContact:
    contact = db.get(InvestorContact, contact_id)
    if contact is None or (not include_deleted and contact.deleted_at is not None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investor contact not found")
    return contact


def create_contact(
    db: Session, payload: InvestorContactCreate, *, actor: Optional[str] = None
) -> InvestorContact:
    # Ensure parent firm exists and is live.
    get_firm(db, payload.firm_id)

    contact = InvestorContact(**payload.model_dump())
    db.add(contact)
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_CONTACT,
        entity_id=contact.id,
        event_type="investor_contact.created",
        summary=f"Created investor contact '{contact.name}'",
        actor=actor,
        details={"contact": _snapshot(contact, CONTACT_FIELDS)},
    )
    db.commit()
    db.refresh(contact)
    return contact


def update_contact(
    db: Session,
    contact_id: int,
    payload: InvestorContactUpdate,
    *,
    actor: Optional[str] = None,
) -> InvestorContact:
    contact = get_contact(db, contact_id)
    before = _snapshot(contact, CONTACT_FIELDS)

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(contact, key, value)
    db.flush()

    after = _snapshot(contact, CONTACT_FIELDS)
    changes = _diff(before, after)
    log_activity(
        db,
        entity_type=ENTITY_CONTACT,
        entity_id=contact.id,
        event_type="investor_contact.updated",
        summary=f"Updated investor contact '{contact.name}'",
        actor=actor,
        details={"changes": changes} if changes else None,
    )
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, contact_id: int, *, actor: Optional[str] = None) -> None:
    contact = get_contact(db, contact_id)
    contact.deleted_at = datetime.now(timezone.utc)
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_CONTACT,
        entity_id=contact.id,
        event_type="investor_contact.deleted",
        summary=f"Soft-deleted investor contact '{contact.name}'",
        actor=actor,
    )
    db.commit()


# ---------------------------------------------------------------------------
# investor_opportunities
# ---------------------------------------------------------------------------

OPPORTUNITY_FIELDS = [
    "firm_id", "primary_contact_id", "stage", "status",
    "amount", "target_close_date", "summary",
    "owner", "next_step", "next_step_due_at",
    "fit_score", "probability_score", "strategic_value_score",
]


def list_opportunities(
    db: Session,
    *,
    firm_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    include_deleted: bool = False,
) -> list[InvestorOpportunity]:
    stmt = select(InvestorOpportunity)
    if firm_id is not None:
        stmt = stmt.where(InvestorOpportunity.firm_id == firm_id)
    if status_filter is not None:
        stmt = stmt.where(InvestorOpportunity.status == status_filter)
    if not include_deleted:
        stmt = stmt.where(InvestorOpportunity.deleted_at.is_(None))
    stmt = stmt.order_by(InvestorOpportunity.id.desc()).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def get_opportunity(
    db: Session, opportunity_id: int, *, include_deleted: bool = False
) -> InvestorOpportunity:
    opp = db.get(InvestorOpportunity, opportunity_id)
    if opp is None or (not include_deleted and opp.deleted_at is not None):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investor opportunity not found")
    return opp


def create_opportunity(
    db: Session, payload: InvestorOpportunityCreate, *, actor: Optional[str] = None
) -> InvestorOpportunity:
    get_firm(db, payload.firm_id)
    if payload.primary_contact_id is not None:
        get_contact(db, payload.primary_contact_id)

    opp = InvestorOpportunity(**payload.model_dump())
    db.add(opp)
    db.flush()

    firm = db.get(InvestorFirm, opp.firm_id)
    firm_name = firm.name if firm else f"firm:{opp.firm_id}"

    log_activity(
        db,
        entity_type=ENTITY_OPPORTUNITY,
        entity_id=opp.id,
        event_type="investor_opportunity.created",
        summary=f"Created opportunity for '{firm_name}' at stage '{opp.stage}'",
        actor=actor,
        details={"opportunity": _snapshot(opp, OPPORTUNITY_FIELDS)},
    )
    db.commit()
    db.refresh(opp)
    return opp


def update_opportunity(
    db: Session,
    opportunity_id: int,
    payload: InvestorOpportunityUpdate,
    *,
    actor: Optional[str] = None,
) -> InvestorOpportunity:
    opp = get_opportunity(db, opportunity_id)
    before = _snapshot(opp, OPPORTUNITY_FIELDS)

    updates = payload.model_dump(exclude_unset=True)
    if "primary_contact_id" in updates and updates["primary_contact_id"] is not None:
        get_contact(db, updates["primary_contact_id"])
    for key, value in updates.items():
        setattr(opp, key, value)
    db.flush()

    after = _snapshot(opp, OPPORTUNITY_FIELDS)
    changes = _diff(before, after)
    log_activity(
        db,
        entity_type=ENTITY_OPPORTUNITY,
        entity_id=opp.id,
        event_type="investor_opportunity.updated",
        summary=f"Updated opportunity #{opp.id} (stage '{opp.stage}', status '{opp.status}')",
        actor=actor,
        details={"changes": changes} if changes else None,
    )
    db.commit()
    db.refresh(opp)
    return opp


def delete_opportunity(
    db: Session, opportunity_id: int, *, actor: Optional[str] = None
) -> None:
    opp = get_opportunity(db, opportunity_id)
    opp.deleted_at = datetime.now(timezone.utc)
    db.flush()

    log_activity(
        db,
        entity_type=ENTITY_OPPORTUNITY,
        entity_id=opp.id,
        event_type="investor_opportunity.deleted",
        summary=f"Soft-deleted investor opportunity #{opp.id}",
        actor=actor,
    )
    db.commit()
