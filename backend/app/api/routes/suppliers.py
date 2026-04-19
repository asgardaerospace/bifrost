"""HTTP endpoints for Supplier OS."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.program import Program
from app.models.supplier import Supplier
from app.schemas.supplier import (
    OnboardingPipelineSummary,
    ProgramSupplierCreate,
    ProgramSupplierRead,
    ProgramSupplierUpdate,
    SupplierCapabilityCreate,
    SupplierCapabilityRead,
    SupplierCertificationCreate,
    SupplierCertificationRead,
    SupplierCertificationUpdate,
    SupplierCreate,
    SupplierDetail,
    SupplierRead,
    SupplierUpdate,
)
from app.services import supplier as supplier_service

router = APIRouter()


def _hydrate_link(db: Session, link) -> ProgramSupplierRead:
    sup = db.get(Supplier, link.supplier_id)
    prog = db.get(Program, link.program_id)
    return ProgramSupplierRead.model_validate(link).model_copy(
        update={
            "supplier_name": sup.name if sup else None,
            "program_name": prog.name if prog else None,
        }
    )


# --- suppliers ---------------------------------------------------------------


@router.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(
    type: Optional[str] = Query(None),
    region: Optional[str] = None,
    country: Optional[str] = None,
    onboarding_status: Optional[str] = None,
    capability: Optional[str] = None,
    certification: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SupplierRead]:
    rows = supplier_service.list_suppliers(
        db,
        type_=type,
        region=region,
        country=country,
        onboarding_status=onboarding_status,
        capability=capability,
        certification=certification,
        skip=skip,
        limit=limit,
    )
    return [SupplierRead.model_validate(r) for r in rows]


@router.get("/suppliers/qualified", response_model=list[SupplierRead])
def list_qualified_suppliers(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SupplierRead]:
    rows = supplier_service.list_qualified_suppliers(db, limit=limit)
    return [SupplierRead.model_validate(r) for r in rows]


@router.get("/suppliers/by-capability")
def suppliers_by_capability(
    db: Session = Depends(get_db),
) -> dict[str, list[SupplierRead]]:
    grouped = supplier_service.suppliers_by_capability(db)
    return {
        cap: [SupplierRead.model_validate(s) for s in sups]
        for cap, sups in grouped.items()
    }


@router.get("/suppliers/by-region")
def suppliers_by_region(
    db: Session = Depends(get_db),
) -> dict[str, list[SupplierRead]]:
    grouped = supplier_service.suppliers_by_region(db)
    return {
        region: [SupplierRead.model_validate(s) for s in sups]
        for region, sups in grouped.items()
    }


@router.get(
    "/suppliers/onboarding/summary", response_model=OnboardingPipelineSummary
)
def onboarding_summary(
    db: Session = Depends(get_db),
) -> OnboardingPipelineSummary:
    return OnboardingPipelineSummary(**supplier_service.onboarding_summary(db))


@router.get("/suppliers/{supplier_id}", response_model=SupplierDetail)
def get_supplier(
    supplier_id: int, db: Session = Depends(get_db)
) -> SupplierDetail:
    sup = supplier_service.get_supplier(db, supplier_id)
    read = SupplierDetail.model_validate(sup)
    # hydrate program_links with program name
    links = [_hydrate_link(db, l) for l in sup.program_links]
    return read.model_copy(update={"program_links": links})


@router.post(
    "/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED
)
def create_supplier(
    payload: SupplierCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> SupplierRead:
    return SupplierRead.model_validate(
        supplier_service.create_supplier(db, payload, actor=actor)
    )


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> SupplierRead:
    return SupplierRead.model_validate(
        supplier_service.update_supplier(db, supplier_id, payload, actor=actor)
    )


# --- capabilities ------------------------------------------------------------


@router.get(
    "/suppliers/{supplier_id}/capabilities",
    response_model=list[SupplierCapabilityRead],
)
def list_capabilities(
    supplier_id: int, db: Session = Depends(get_db)
) -> list[SupplierCapabilityRead]:
    rows = supplier_service.list_supplier_capabilities(db, supplier_id)
    return [SupplierCapabilityRead.model_validate(r) for r in rows]


@router.post(
    "/supplier-capabilities",
    response_model=SupplierCapabilityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_capability(
    payload: SupplierCapabilityCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> SupplierCapabilityRead:
    return SupplierCapabilityRead.model_validate(
        supplier_service.create_supplier_capability(db, payload, actor=actor)
    )


@router.delete(
    "/supplier-capabilities/{capability_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_capability(
    capability_id: int,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> None:
    supplier_service.delete_supplier_capability(db, capability_id, actor=actor)


# --- certifications ----------------------------------------------------------


@router.get(
    "/suppliers/{supplier_id}/certifications",
    response_model=list[SupplierCertificationRead],
)
def list_certifications(
    supplier_id: int, db: Session = Depends(get_db)
) -> list[SupplierCertificationRead]:
    rows = supplier_service.list_supplier_certifications(db, supplier_id)
    return [SupplierCertificationRead.model_validate(r) for r in rows]


@router.post(
    "/supplier-certifications",
    response_model=SupplierCertificationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_certification(
    payload: SupplierCertificationCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> SupplierCertificationRead:
    return SupplierCertificationRead.model_validate(
        supplier_service.create_supplier_certification(db, payload, actor=actor)
    )


@router.patch(
    "/supplier-certifications/{cert_id}",
    response_model=SupplierCertificationRead,
)
def update_certification(
    cert_id: int,
    payload: SupplierCertificationUpdate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> SupplierCertificationRead:
    return SupplierCertificationRead.model_validate(
        supplier_service.update_supplier_certification(
            db, cert_id, payload, actor=actor
        )
    )


# --- program <-> supplier links ---------------------------------------------


@router.post(
    "/program-suppliers",
    response_model=ProgramSupplierRead,
    status_code=status.HTTP_201_CREATED,
)
def link_program_supplier(
    payload: ProgramSupplierCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> ProgramSupplierRead:
    link = supplier_service.link_program_supplier(db, payload, actor=actor)
    return _hydrate_link(db, link)


@router.patch(
    "/program-suppliers/{link_id}", response_model=ProgramSupplierRead
)
def update_program_supplier(
    link_id: int,
    payload: ProgramSupplierUpdate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> ProgramSupplierRead:
    link = supplier_service.update_program_supplier(
        db, link_id, payload, actor=actor
    )
    return _hydrate_link(db, link)


@router.get(
    "/programs/{program_id}/suppliers",
    response_model=list[ProgramSupplierRead],
)
def list_program_suppliers(
    program_id: int, db: Session = Depends(get_db)
) -> list[ProgramSupplierRead]:
    rows = supplier_service.list_program_suppliers(db, program_id=program_id)
    return [_hydrate_link(db, l) for l in rows]


@router.get(
    "/suppliers/{supplier_id}/programs",
    response_model=list[ProgramSupplierRead],
)
def list_supplier_programs(
    supplier_id: int, db: Session = Depends(get_db)
) -> list[ProgramSupplierRead]:
    rows = supplier_service.list_program_suppliers(db, supplier_id=supplier_id)
    return [_hydrate_link(db, l) for l in rows]
