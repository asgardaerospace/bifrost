"""Graph Intelligence Layer — relationship mapping service.

Derives rule-based edges across Capital / Market / Program / Supplier
domains. No new persistence, no ML — just deterministic scoring over the
existing models.

All scoring weights are module-level constants so operators can inspect
and tune them without tracing model calls. Functions return typed Pydantic
schemas from ``app.schemas.graph`` so routes and downstream consumers (the
Executive OS, the Command Console) can reuse the same shapes.

Design notes
------------

* A Program's "sector" is its linked Account's sector.
* A Program's "region" is its linked Account's region.
* Investors have no structured sector field — we match against
  ``InvestorFirm.description`` + ``stage_focus`` + ``location`` as a text
  corpus (lowercased, word-boundary aware).
* Suppliers are matched to programs via capability keywords found in the
  program's name/description, plus region parity and certification
  strength.
* ``already_linked`` is reported but does not dampen the score — callers
  can filter or surface as "confirmed partners".
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.investor import InvestorFirm
from app.models.market import Account
from app.models.program import Program, ProgramAccount, ProgramInvestor
from app.models.supplier import (
    ProgramSupplier,
    Supplier,
    SupplierCapability,
    SupplierCertification,
)
from app.schemas.graph import (
    AccountProgramMatches,
    InvestorMatch,
    InvestorProgramMatches,
    ProgramInvestorMatches,
    ProgramMatch,
    ProgramSupplierMatches,
    SupplierMatch,
)

# ---------------------------------------------------------------------------
# scoring weights (tunable, inspectable)
# ---------------------------------------------------------------------------

# program → investor
W_INV_SECTOR_MATCH = 30
W_INV_STAGE_MATCH = 20
W_INV_LOCATION_MATCH = 10
W_INV_STRATEGIC_VALUE = 30  # scaled by program.strategic_value_score / 100
W_INV_HIGH_VALUE_PROGRAM = 10  # program.estimated_value >= 1M

# program → supplier
W_SUP_CAPABILITY_MATCH = 25  # per matched capability (capped at 50)
W_SUP_CAPABILITY_CAP = 50
W_SUP_CERT_STRONG = 15  # AS9100/NADCAP/ITAR
W_SUP_REGION_MATCH = 15
W_SUP_QUALIFIED = 15
W_SUP_ONBOARDED = 20
W_SUP_PREFERRED_PARTNER = 10  # scaled by preferred_partner_score/100

# account → program
W_ACCT_DIRECT_OWNER = 50
W_ACCT_DIRECT_LINK = 40
W_ACCT_SECTOR_MATCH = 25
W_ACCT_REGION_MATCH = 10
W_ACCT_STRATEGIC_VALUE = 20

# investor → program
W_INVP_DIRECT_LINK = 50
W_INVP_SECTOR_MATCH = 25
W_INVP_STAGE_MATCH = 15
W_INVP_STRATEGIC_VALUE = 25

HIGH_VALUE_THRESHOLD = 1_000_000.0
STRONG_CERTS = ("AS9100", "NADCAP", "ITAR")

# program.stage → investor.stage_focus keyword buckets
STAGE_FOCUS_BUCKETS: dict[str, tuple[str, ...]] = {
    "identified": ("seed", "pre-seed", "series a", "early"),
    "pursuing": ("series a", "series b", "early", "growth"),
    "active": ("growth", "series b", "series c", "late", "strategic"),
    "won": ("growth", "late", "strategic"),
    "lost": (),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clip(score: float) -> int:
    return max(0, min(100, int(round(score))))


def _tokenize(text: Optional[str]) -> set[str]:
    if not text:
        return set()
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if t}


def _contains_any(text: Optional[str], terms: Iterable[str]) -> list[str]:
    if not text:
        return []
    lower = text.lower()
    return [t for t in terms if t and t.lower() in lower]


# ---------------------------------------------------------------------------
# loaders (shared; callers pre-fetch to avoid N+1)
# ---------------------------------------------------------------------------


def _load_program(db: Session, program_id: int) -> Program:
    stmt = (
        select(Program)
        .where(Program.id == program_id)
        .where(Program.deleted_at.is_(None))
    )
    prog = db.execute(stmt).scalar_one_or_none()
    if prog is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Program #{program_id} not found")
    return prog


def _load_account(db: Session, account_id: int) -> Account:
    stmt = (
        select(Account)
        .where(Account.id == account_id)
        .where(Account.deleted_at.is_(None))
    )
    acct = db.execute(stmt).scalar_one_or_none()
    if acct is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Account #{account_id} not found")
    return acct


def _load_investor(db: Session, investor_id: int) -> InvestorFirm:
    stmt = (
        select(InvestorFirm)
        .where(InvestorFirm.id == investor_id)
        .where(InvestorFirm.deleted_at.is_(None))
    )
    inv = db.execute(stmt).scalar_one_or_none()
    if inv is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Investor #{investor_id} not found")
    return inv


# ---------------------------------------------------------------------------
# program → investors
# ---------------------------------------------------------------------------

PROGRAM_INVESTOR_LOGIC = (
    f"Investor score = sector_match({W_INV_SECTOR_MATCH}) + "
    f"stage_match({W_INV_STAGE_MATCH}) + location_match({W_INV_LOCATION_MATCH}) "
    f"+ strategic_value(0..{W_INV_STRATEGIC_VALUE}) "
    f"+ high_value_program({W_INV_HIGH_VALUE_PROGRAM}). Clipped to [0,100]."
)


def _program_account(db: Session, program: Program) -> Optional[Account]:
    if program.account_id is None:
        return None
    return db.get(Account, program.account_id)


def _investor_corpus(inv: InvestorFirm) -> str:
    parts = [inv.name, inv.stage_focus or "", inv.location or "", inv.description or ""]
    return " ".join(p for p in parts if p)


def match_investors_for_program(
    db: Session, program_id: int, *, limit: int = 25
) -> ProgramInvestorMatches:
    prog = _load_program(db, program_id)
    account = _program_account(db, prog)
    sector = (account.sector or "").strip() if account else ""
    region = (account.region or "").strip() if account else ""
    stage_terms = STAGE_FOCUS_BUCKETS.get(prog.stage, ())
    strategic = prog.strategic_value_score or 0
    high_value = (
        prog.estimated_value is not None
        and float(prog.estimated_value) >= HIGH_VALUE_THRESHOLD
    )

    existing_links = {
        pi.investor_id: pi.relevance_type
        for pi in db.execute(
            select(ProgramInvestor).where(ProgramInvestor.program_id == program_id)
        ).scalars().all()
    }

    firms = (
        db.execute(
            select(InvestorFirm)
            .where(InvestorFirm.deleted_at.is_(None))
            .where(InvestorFirm.status == "active")
        )
        .scalars()
        .all()
    )

    matches: list[InvestorMatch] = []
    for inv in firms:
        score = 0.0
        factors: list[str] = []
        corpus = _investor_corpus(inv)

        if sector and sector.lower() in corpus.lower():
            score += W_INV_SECTOR_MATCH
            factors.append(f"sector match: {sector}")

        if stage_terms:
            hits = _contains_any(inv.stage_focus, stage_terms)
            if hits:
                score += W_INV_STAGE_MATCH
                factors.append(f"stage focus: {', '.join(hits)}")

        if region and inv.location and region.lower() in inv.location.lower():
            score += W_INV_LOCATION_MATCH
            factors.append(f"region match: {region}")

        if strategic:
            bump = W_INV_STRATEGIC_VALUE * (strategic / 100.0)
            score += bump
            factors.append(f"program strategic_value={strategic}")

        if high_value:
            score += W_INV_HIGH_VALUE_PROGRAM
            factors.append("program is high-value")

        if score <= 0 and inv.id not in existing_links:
            continue

        matches.append(
            InvestorMatch(
                investor_id=inv.id,
                investor_name=inv.name,
                stage_focus=inv.stage_focus,
                location=inv.location,
                score=_clip(score),
                factors=factors or ["no positive signals — informational"],
                already_linked=inv.id in existing_links,
                relevance_type=existing_links.get(inv.id),
            )
        )

    matches.sort(key=lambda m: (-m.score, m.investor_name))
    return ProgramInvestorMatches(
        program_id=prog.id,
        program_name=prog.name,
        generated_at=_now(),
        scoring_logic=PROGRAM_INVESTOR_LOGIC,
        matches=matches[:limit],
    )


# ---------------------------------------------------------------------------
# program → suppliers
# ---------------------------------------------------------------------------

PROGRAM_SUPPLIER_LOGIC = (
    f"Supplier score = capability_matches*{W_SUP_CAPABILITY_MATCH} "
    f"(cap {W_SUP_CAPABILITY_CAP}) + strong_cert_count*{W_SUP_CERT_STRONG} "
    f"+ region_match({W_SUP_REGION_MATCH}) + qualified({W_SUP_QUALIFIED}) "
    f"+ onboarded({W_SUP_ONBOARDED}) + preferred(0..{W_SUP_PREFERRED_PARTNER}). "
    "Clipped to [0,100]."
)


def _program_keywords(prog: Program) -> set[str]:
    return _tokenize(prog.name) | _tokenize(prog.description)


def match_suppliers_for_program(
    db: Session, program_id: int, *, limit: int = 25
) -> ProgramSupplierMatches:
    prog = _load_program(db, program_id)
    account = _program_account(db, prog)
    region = (account.region or "").strip() if account else ""
    keywords = _program_keywords(prog)

    existing_links = {
        ps.supplier_id: (ps.role, ps.status)
        for ps in db.execute(
            select(ProgramSupplier).where(ProgramSupplier.program_id == program_id)
        ).scalars().all()
    }

    suppliers = (
        db.execute(
            select(Supplier)
            .where(Supplier.deleted_at.is_(None))
            .options(
                selectinload(Supplier.capabilities),
                selectinload(Supplier.certifications),
            )
        )
        .scalars()
        .all()
    )

    matches: list[SupplierMatch] = []
    for sup in suppliers:
        score = 0.0
        factors: list[str] = []

        cap_names = [c.capability_type for c in sup.capabilities]
        matched_caps = [
            c for c in cap_names if _tokenize(c) & keywords
        ]
        if matched_caps:
            bump = min(
                W_SUP_CAPABILITY_CAP,
                len(matched_caps) * W_SUP_CAPABILITY_MATCH,
            )
            score += bump
            factors.append(f"capability match: {', '.join(matched_caps)}")

        active_certs = [
            c.certification for c in sup.certifications if c.status == "active"
        ]
        strong = [c for c in active_certs if c in STRONG_CERTS]
        if strong:
            score += len(strong) * W_SUP_CERT_STRONG
            factors.append(f"strong certifications: {', '.join(strong)}")

        if region and sup.region and sup.region.lower() == region.lower():
            score += W_SUP_REGION_MATCH
            factors.append(f"region match: {region}")

        if sup.onboarding_status == "onboarded":
            score += W_SUP_ONBOARDED
            factors.append("supplier onboarded")
        elif sup.onboarding_status == "qualified":
            score += W_SUP_QUALIFIED
            factors.append("supplier qualified")

        if sup.preferred_partner_score:
            bump = W_SUP_PREFERRED_PARTNER * (sup.preferred_partner_score / 100.0)
            score += bump
            factors.append(f"preferred_partner_score={sup.preferred_partner_score}")

        if score <= 0 and sup.id not in existing_links:
            continue

        role, status = existing_links.get(sup.id, (None, None))

        matches.append(
            SupplierMatch(
                supplier_id=sup.id,
                supplier_name=sup.name,
                type=sup.type,
                region=sup.region,
                onboarding_status=sup.onboarding_status,
                preferred_partner_score=sup.preferred_partner_score,
                capabilities=cap_names,
                certifications=active_certs,
                score=_clip(score),
                factors=factors or ["no positive signals — informational"],
                already_linked=sup.id in existing_links,
                role=role,
                status=status,
            )
        )

    matches.sort(key=lambda m: (-m.score, m.supplier_name))
    return ProgramSupplierMatches(
        program_id=prog.id,
        program_name=prog.name,
        generated_at=_now(),
        scoring_logic=PROGRAM_SUPPLIER_LOGIC,
        matches=matches[:limit],
    )


# ---------------------------------------------------------------------------
# account → programs
# ---------------------------------------------------------------------------

ACCOUNT_PROGRAM_LOGIC = (
    f"Program score (from account) = owner({W_ACCT_DIRECT_OWNER}) | "
    f"linked_role({W_ACCT_DIRECT_LINK}) | sector_match({W_ACCT_SECTOR_MATCH}) "
    f"+ region_match({W_ACCT_REGION_MATCH}) "
    f"+ strategic_value(0..{W_ACCT_STRATEGIC_VALUE}). Clipped to [0,100]."
)


def match_programs_for_account(
    db: Session, account_id: int, *, limit: int = 25
) -> AccountProgramMatches:
    acct = _load_account(db, account_id)
    sector = (acct.sector or "").strip()
    region = (acct.region or "").strip()

    linked_roles = {
        pa.program_id: pa.role
        for pa in db.execute(
            select(ProgramAccount).where(ProgramAccount.account_id == account_id)
        ).scalars().all()
    }

    programs = (
        db.execute(
            select(Program).where(Program.deleted_at.is_(None))
        )
        .scalars()
        .all()
    )
    account_ids = {p.account_id for p in programs if p.account_id}
    accounts_by_id: dict[int, Account] = {}
    if account_ids:
        rows = db.execute(
            select(Account).where(Account.id.in_(account_ids))
        ).scalars().all()
        accounts_by_id = {a.id: a for a in rows}

    matches: list[ProgramMatch] = []
    for p in programs:
        score = 0.0
        factors: list[str] = []
        role: Optional[str] = None

        if p.account_id == account_id:
            score += W_ACCT_DIRECT_OWNER
            factors.append("owning account")
            role = "owner"
        elif p.id in linked_roles:
            score += W_ACCT_DIRECT_LINK
            role = linked_roles[p.id]
            factors.append(f"linked as {role}")

        other = accounts_by_id.get(p.account_id) if p.account_id else None
        if (
            sector
            and other is not None
            and (other.sector or "").lower() == sector.lower()
            and p.account_id != account_id
        ):
            score += W_ACCT_SECTOR_MATCH
            factors.append(f"shared sector: {sector}")

        if (
            region
            and other is not None
            and (other.region or "").lower() == region.lower()
            and p.account_id != account_id
        ):
            score += W_ACCT_REGION_MATCH
            factors.append(f"shared region: {region}")

        if p.strategic_value_score:
            bump = W_ACCT_STRATEGIC_VALUE * (p.strategic_value_score / 100.0)
            score += bump
            factors.append(f"program strategic_value={p.strategic_value_score}")

        if score <= 0:
            continue

        matches.append(
            ProgramMatch(
                program_id=p.id,
                program_name=p.name,
                account_id=p.account_id,
                account_name=(accounts_by_id.get(p.account_id).name if accounts_by_id.get(p.account_id) else None),
                stage=p.stage,
                estimated_value=float(p.estimated_value) if p.estimated_value is not None else None,
                strategic_value_score=p.strategic_value_score,
                score=_clip(score),
                factors=factors,
                already_linked=(p.account_id == account_id or p.id in linked_roles),
                link_role=role,
            )
        )

    matches.sort(key=lambda m: (-m.score, m.program_name))
    return AccountProgramMatches(
        account_id=acct.id,
        account_name=acct.name,
        generated_at=_now(),
        scoring_logic=ACCOUNT_PROGRAM_LOGIC,
        matches=matches[:limit],
    )


# ---------------------------------------------------------------------------
# investor → programs
# ---------------------------------------------------------------------------

INVESTOR_PROGRAM_LOGIC = (
    f"Program score (from investor) = direct_link({W_INVP_DIRECT_LINK}) "
    f"+ sector_match({W_INVP_SECTOR_MATCH}) "
    f"+ stage_match({W_INVP_STAGE_MATCH}) "
    f"+ strategic_value(0..{W_INVP_STRATEGIC_VALUE}). Clipped to [0,100]."
)


def match_programs_for_investor(
    db: Session, investor_id: int, *, limit: int = 25
) -> InvestorProgramMatches:
    inv = _load_investor(db, investor_id)
    corpus = _investor_corpus(inv).lower()

    linked = {
        pi.program_id: pi.relevance_type
        for pi in db.execute(
            select(ProgramInvestor).where(ProgramInvestor.investor_id == investor_id)
        ).scalars().all()
    }

    programs = (
        db.execute(
            select(Program).where(Program.deleted_at.is_(None))
        )
        .scalars()
        .all()
    )
    account_ids = {p.account_id for p in programs if p.account_id}
    accounts_by_id: dict[int, Account] = {}
    if account_ids:
        rows = db.execute(
            select(Account).where(Account.id.in_(account_ids))
        ).scalars().all()
        accounts_by_id = {a.id: a for a in rows}

    matches: list[ProgramMatch] = []
    for p in programs:
        score = 0.0
        factors: list[str] = []
        relevance: Optional[str] = None

        if p.id in linked:
            score += W_INVP_DIRECT_LINK
            relevance = linked[p.id]
            factors.append(f"direct link ({relevance})")

        acct = accounts_by_id.get(p.account_id) if p.account_id else None
        if acct and acct.sector and acct.sector.lower() in corpus:
            score += W_INVP_SECTOR_MATCH
            factors.append(f"thesis mentions sector: {acct.sector}")

        stage_terms = STAGE_FOCUS_BUCKETS.get(p.stage, ())
        hits = _contains_any(inv.stage_focus, stage_terms)
        if hits:
            score += W_INVP_STAGE_MATCH
            factors.append(f"stage alignment: {', '.join(hits)}")

        if p.strategic_value_score:
            bump = W_INVP_STRATEGIC_VALUE * (p.strategic_value_score / 100.0)
            score += bump
            factors.append(f"strategic_value={p.strategic_value_score}")

        if score <= 0:
            continue

        matches.append(
            ProgramMatch(
                program_id=p.id,
                program_name=p.name,
                account_id=p.account_id,
                account_name=acct.name if acct else None,
                stage=p.stage,
                estimated_value=float(p.estimated_value) if p.estimated_value is not None else None,
                strategic_value_score=p.strategic_value_score,
                score=_clip(score),
                factors=factors,
                already_linked=p.id in linked,
                relevance_type=relevance,
            )
        )

    matches.sort(key=lambda m: (-m.score, m.program_name))
    return InvestorProgramMatches(
        investor_id=inv.id,
        investor_name=inv.name,
        generated_at=_now(),
        scoring_logic=INVESTOR_PROGRAM_LOGIC,
        matches=matches[:limit],
    )
