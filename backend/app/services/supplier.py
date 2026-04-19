"""Supplier OS services — CRUD, capability search, program linkage."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.program import Program
from app.models.supplier import (
    ProgramSupplier,
    Supplier,
    SupplierCapability,
    SupplierCertification,
)
from app.schemas.supplier import (
    ProgramSupplierCreate,
    ProgramSupplierUpdate,
    SupplierCapabilityCreate,
    SupplierCertificationCreate,
    SupplierCertificationUpdate,
    SupplierCreate,
    SupplierUpdate,
)
from app.services.activity import log_activity

ENTITY_SUPPLIER = "supplier"
ENTITY_SUPPLIER_CAPABILITY = "supplier_capability"
ENTITY_SUPPLIER_CERT = "supplier_certification"
ENTITY_PROGRAM_SUPPLIER = "program_supplier"

QUALIFIED_STATUSES = ("qualified", "onboarded")
ACTIVE_PROGRAM_STAGES = ("pursuing", "active")


def _not_found(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"{name} not found"
    )


# ---------------------------------------------------------------------------
# suppliers
# ---------------------------------------------------------------------------

def list_suppliers(
    db: Session,
    *,
    type_: Optional[str] = None,
    region: Optional[str] = None,
    country: Optional[str] = None,
    onboarding_status: Optional[str] = None,
    capability: Optional[str] = None,
    certification: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Supplier]:
    stmt = select(Supplier).where(Supplier.deleted_at.is_(None))
    if type_:
        stmt = stmt.where(Supplier.type == type_)
    if region:
        stmt = stmt.where(Supplier.region == region)
    if country:
        stmt = stmt.where(Supplier.country == country)
    if onboarding_status:
        stmt = stmt.where(Supplier.onboarding_status == onboarding_status)
    if capability:
        stmt = (
            stmt.join(
                SupplierCapability,
                SupplierCapability.supplier_id == Supplier.id,
            )
            .where(SupplierCapability.capability_type == capability)
            .distinct()
        )
    if certification:
        stmt = (
            stmt.join(
                SupplierCertification,
                SupplierCertification.supplier_id == Supplier.id,
            )
            .where(SupplierCertification.certification == certification)
            .where(SupplierCertification.status == "active")
            .distinct()
        )
    stmt = stmt.order_by(Supplier.name).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_qualified_suppliers(
    db: Session, *, limit: int = 100
) -> list[Supplier]:
    stmt = (
        select(Supplier)
        .where(Supplier.deleted_at.is_(None))
        .where(Supplier.onboarding_status.in_(QUALIFIED_STATUSES))
        .order_by(
            desc(Supplier.preferred_partner_score.is_not(None)),
            desc(Supplier.preferred_partner_score),
            Supplier.name,
        )
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def suppliers_by_capability(
    db: Session, *, limit_per_bucket: int = 50
) -> dict[str, list[Supplier]]:
    rows = db.execute(
        select(SupplierCapability.capability_type, Supplier)
        .join(Supplier, Supplier.id == SupplierCapability.supplier_id)
        .where(Supplier.deleted_at.is_(None))
        .order_by(SupplierCapability.capability_type, Supplier.name)
    ).all()
    grouped: dict[str, list[Supplier]] = {}
    for cap, sup in rows:
        bucket = grouped.setdefault(cap, [])
        if len(bucket) < limit_per_bucket:
            bucket.append(sup)
    return grouped


def suppliers_by_region(
    db: Session, *, limit_per_bucket: int = 50
) -> dict[str, list[Supplier]]:
    rows = db.execute(
        select(Supplier).where(Supplier.deleted_at.is_(None)).order_by(
            Supplier.region, Supplier.name
        )
    ).scalars().all()
    grouped: dict[str, list[Supplier]] = {}
    for sup in rows:
        key = sup.region or "_unknown"
        bucket = grouped.setdefault(key, [])
        if len(bucket) < limit_per_bucket:
            bucket.append(sup)
    return grouped


def get_supplier(db: Session, supplier_id: int) -> Supplier:
    sup = db.execute(
        select(Supplier)
        .where(Supplier.id == supplier_id)
        .where(Supplier.deleted_at.is_(None))
        .options(
            selectinload(Supplier.capabilities),
            selectinload(Supplier.certifications),
            selectinload(Supplier.program_links),
        )
    ).scalar_one_or_none()
    if sup is None:
        raise _not_found("Supplier")
    return sup


def create_supplier(
    db: Session, payload: SupplierCreate, *, actor: Optional[str] = None
) -> Supplier:
    sup = Supplier(**payload.model_dump())
    db.add(sup)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_SUPPLIER,
        entity_id=sup.id,
        event_type="supplier.created",
        summary=f"Supplier '{sup.name}' created",
        actor=actor,
        details={
            "type": sup.type,
            "region": sup.region,
            "onboarding_status": sup.onboarding_status,
        },
    )
    db.commit()
    db.refresh(sup)
    return sup


def update_supplier(
    db: Session,
    supplier_id: int,
    payload: SupplierUpdate,
    *,
    actor: Optional[str] = None,
) -> Supplier:
    sup = db.get(Supplier, supplier_id)
    if sup is None or sup.deleted_at is not None:
        raise _not_found("Supplier")
    changes = payload.model_dump(exclude_unset=True)
    prev_status = sup.onboarding_status
    for k, v in changes.items():
        setattr(sup, k, v)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_SUPPLIER,
        entity_id=sup.id,
        event_type="supplier.updated",
        summary=f"Supplier '{sup.name}' updated",
        actor=actor,
        details={"changes": changes},
    )
    if (
        "onboarding_status" in changes
        and changes["onboarding_status"] != prev_status
    ):
        log_activity(
            db,
            entity_type=ENTITY_SUPPLIER,
            entity_id=sup.id,
            event_type="supplier.onboarding_status_changed",
            summary=(
                f"Supplier '{sup.name}' onboarding {prev_status} → {sup.onboarding_status}"
            ),
            actor=actor,
            details={"from": prev_status, "to": sup.onboarding_status},
        )
    db.commit()
    db.refresh(sup)
    return sup


# ---------------------------------------------------------------------------
# capabilities
# ---------------------------------------------------------------------------

def list_supplier_capabilities(
    db: Session, supplier_id: int
) -> list[SupplierCapability]:
    get_supplier(db, supplier_id)
    stmt = (
        select(SupplierCapability)
        .where(SupplierCapability.supplier_id == supplier_id)
        .order_by(SupplierCapability.capability_type)
    )
    return list(db.execute(stmt).scalars().all())


def create_supplier_capability(
    db: Session,
    payload: SupplierCapabilityCreate,
    *,
    actor: Optional[str] = None,
) -> SupplierCapability:
    get_supplier(db, payload.supplier_id)
    row = SupplierCapability(**payload.model_dump())
    db.add(row)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_SUPPLIER_CAPABILITY,
        entity_id=row.id,
        event_type="supplier_capability.added",
        summary=(
            f"Capability '{row.capability_type}' added to supplier #{row.supplier_id}"
        ),
        actor=actor,
        details={"supplier_id": row.supplier_id, "type": row.capability_type},
    )
    db.commit()
    db.refresh(row)
    return row


def delete_supplier_capability(
    db: Session, capability_id: int, *, actor: Optional[str] = None
) -> None:
    row = db.get(SupplierCapability, capability_id)
    if row is None:
        raise _not_found("Supplier capability")
    supplier_id = row.supplier_id
    cap_type = row.capability_type
    db.delete(row)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_SUPPLIER_CAPABILITY,
        entity_id=capability_id,
        event_type="supplier_capability.removed",
        summary=f"Capability '{cap_type}' removed from supplier #{supplier_id}",
        actor=actor,
        details={"supplier_id": supplier_id, "type": cap_type},
    )
    db.commit()


# ---------------------------------------------------------------------------
# certifications
# ---------------------------------------------------------------------------

def list_supplier_certifications(
    db: Session, supplier_id: int
) -> list[SupplierCertification]:
    get_supplier(db, supplier_id)
    stmt = (
        select(SupplierCertification)
        .where(SupplierCertification.supplier_id == supplier_id)
        .order_by(SupplierCertification.certification)
    )
    return list(db.execute(stmt).scalars().all())


def create_supplier_certification(
    db: Session,
    payload: SupplierCertificationCreate,
    *,
    actor: Optional[str] = None,
) -> SupplierCertification:
    get_supplier(db, payload.supplier_id)
    row = SupplierCertification(**payload.model_dump())
    db.add(row)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_SUPPLIER_CERT,
        entity_id=row.id,
        event_type="supplier_certification.added",
        summary=(
            f"Certification '{row.certification}' ({row.status}) added to supplier #{row.supplier_id}"
        ),
        actor=actor,
        details={
            "supplier_id": row.supplier_id,
            "certification": row.certification,
            "status": row.status,
        },
    )
    db.commit()
    db.refresh(row)
    return row


def update_supplier_certification(
    db: Session,
    cert_id: int,
    payload: SupplierCertificationUpdate,
    *,
    actor: Optional[str] = None,
) -> SupplierCertification:
    row = db.get(SupplierCertification, cert_id)
    if row is None:
        raise _not_found("Supplier certification")
    changes = payload.model_dump(exclude_unset=True)
    prev_status = row.status
    for k, v in changes.items():
        setattr(row, k, v)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_SUPPLIER_CERT,
        entity_id=row.id,
        event_type="supplier_certification.updated",
        summary=(
            f"Certification '{row.certification}' on supplier #{row.supplier_id} updated"
        ),
        actor=actor,
        details={"changes": changes},
    )
    if "status" in changes and changes["status"] != prev_status:
        log_activity(
            db,
            entity_type=ENTITY_SUPPLIER_CERT,
            entity_id=row.id,
            event_type="supplier_certification.status_changed",
            summary=(
                f"Certification '{row.certification}' status {prev_status} → {row.status}"
            ),
            actor=actor,
            details={"from": prev_status, "to": row.status},
        )
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# program <-> supplier linkage
# ---------------------------------------------------------------------------

def _assert_program(db: Session, program_id: int) -> Program:
    prog = db.get(Program, program_id)
    if prog is None or prog.deleted_at is not None:
        raise HTTPException(
            status_code=404, detail=f"Program #{program_id} not found"
        )
    return prog


def link_program_supplier(
    db: Session,
    payload: ProgramSupplierCreate,
    *,
    actor: Optional[str] = None,
) -> ProgramSupplier:
    _assert_program(db, payload.program_id)
    get_supplier(db, payload.supplier_id)
    existing = db.execute(
        select(ProgramSupplier).where(
            and_(
                ProgramSupplier.program_id == payload.program_id,
                ProgramSupplier.supplier_id == payload.supplier_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Supplier is already linked to this program",
        )
    link = ProgramSupplier(**payload.model_dump())
    db.add(link)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_PROGRAM_SUPPLIER,
        entity_id=link.id,
        event_type="program_supplier.linked",
        summary=(
            f"Supplier #{link.supplier_id} linked to program #{link.program_id} as {link.role}/{link.status}"
        ),
        actor=actor,
        details={
            "program_id": link.program_id,
            "supplier_id": link.supplier_id,
            "role": link.role,
            "status": link.status,
        },
    )
    db.commit()
    db.refresh(link)
    return link


def update_program_supplier(
    db: Session,
    link_id: int,
    payload: ProgramSupplierUpdate,
    *,
    actor: Optional[str] = None,
) -> ProgramSupplier:
    row = db.get(ProgramSupplier, link_id)
    if row is None:
        raise _not_found("Program/Supplier link")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(row, k, v)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_PROGRAM_SUPPLIER,
        entity_id=row.id,
        event_type="program_supplier.updated",
        summary=(
            f"Program #{row.program_id} / supplier #{row.supplier_id} updated"
        ),
        actor=actor,
        details={"changes": changes},
    )
    db.commit()
    db.refresh(row)
    return row


def list_program_suppliers(
    db: Session,
    *,
    program_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
) -> list[ProgramSupplier]:
    stmt = select(ProgramSupplier)
    if program_id is not None:
        stmt = stmt.where(ProgramSupplier.program_id == program_id)
    if supplier_id is not None:
        stmt = stmt.where(ProgramSupplier.supplier_id == supplier_id)
    stmt = stmt.order_by(desc(ProgramSupplier.updated_at))
    return list(db.execute(stmt).scalars().all())


def find_program_by_name(db: Session, name: str) -> Optional[Program]:
    candidate = name.strip()
    if not candidate:
        return None
    stmt = (
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(func.lower(Program.name) == candidate.lower())
    )
    hit = db.execute(stmt).scalar_one_or_none()
    if hit is not None:
        return hit
    stmt = (
        select(Program)
        .where(Program.deleted_at.is_(None))
        .where(func.lower(Program.name).like(candidate.lower() + "%"))
        .limit(2)
    )
    rows = db.execute(stmt).scalars().all()
    if len(rows) == 1:
        return rows[0]
    return None


# ---------------------------------------------------------------------------
# onboarding pipeline summary
# ---------------------------------------------------------------------------

def onboarding_summary(db: Session) -> dict:
    rows = db.execute(
        select(Supplier).where(Supplier.deleted_at.is_(None))
    ).scalars().all()
    by_status: dict[str, int] = {}
    qualified = 0
    onboarded = 0
    for s in rows:
        by_status[s.onboarding_status] = by_status.get(s.onboarding_status, 0) + 1
        if s.onboarding_status == "qualified":
            qualified += 1
        if s.onboarding_status == "onboarded":
            onboarded += 1

    active_link_count = db.execute(
        select(func.count(ProgramSupplier.id))
        .join(Program, Program.id == ProgramSupplier.program_id)
        .where(Program.deleted_at.is_(None))
        .where(Program.stage.in_(ACTIVE_PROGRAM_STAGES))
    ).scalar_one()

    return {
        "total": len(rows),
        "by_status": by_status,
        "qualified": qualified,
        "onboarded": onboarded,
        "active_program_supplier_count": int(active_link_count or 0),
    }
