"""Transformer for ``programs`` rows.

Produces one note per program at
``Bifrost/Programs/program-{id}.md``. Bundles every relationship the
note needs into ``query_changed`` so ``render`` stays pure.

Performance contract — for a batch of N programs:
    * 1 main query for programs (with selectinload on the primary account)
    * 1 query each for program_accounts/investors/suppliers (joined to
      their parent table to pick up names in one round-trip)
    * 1 query for program_activities
    * 1 query each for meetings/communications/notes filtered with
      ``entity_type='program' AND entity_id IN (...)``

Total ≈ 8 queries regardless of batch size. Communications are
column-selected (not full ORM load) to dodge the existing DB drift on
the optional ``source_system`` columns.

Parent refs cover all three relationship dimensions: the primary
account, every linked investor firm, every linked supplier. The
coordinator's reverse-touch pass will only refresh the parent types
that have a registered transformer — types without one (accounts,
suppliers in the current setup) are silently ignored with a warning,
which is the intended forward-compatible behavior.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.exporters.obsidian.types import NoteDoc, ParentRef, RenderContext
from app.models.communication import Communication
from app.models.investor import InvestorFirm
from app.models.market import Account
from app.models.meeting import Meeting
from app.models.note import Note
from app.models.program import (
    Program,
    ProgramAccount,
    ProgramActivity,
    ProgramInvestor,
)
from app.models.supplier import ProgramSupplier, Supplier


_ENTITY_TYPE = "program"
_PREFIX = "program"
_FOLDER = "Bifrost/Programs"
_ACTIVITY_LIMIT = 10
_MIN_DT = datetime.min.replace(tzinfo=timezone.utc)


# ----------------------------------------------------------------------
# bundles
# ----------------------------------------------------------------------


@dataclass(slots=True)
class _RecentItem:
    kind: str  # "meeting" | "comm" | "note"
    id: int
    display: str
    when: Optional[datetime]


@dataclass(slots=True)
class _ProgramBundle:
    program: Program
    accounts: list[tuple[Account, str]]
    investors: list[tuple[InvestorFirm, str]]
    suppliers: list[tuple[Supplier, str, str]]  # (supplier, role, status)
    activities: list[ProgramActivity]
    recent: list[_RecentItem]

    @property
    def id(self) -> int:
        return self.program.id

    @property
    def deleted_at(self) -> Optional[datetime]:
        return self.program.deleted_at


# ----------------------------------------------------------------------
# transformer
# ----------------------------------------------------------------------


class ProgramTransformer:
    entity_type: str = _ENTITY_TYPE
    prefix: str = _PREFIX

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def query_changed(
        self, db: Session, since: datetime | None
    ) -> Iterable[_ProgramBundle]:
        stmt = (
            select(Program)
            .options(selectinload(Program.account))
            .order_by(Program.id)
        )
        if since is not None:
            stmt = stmt.where(
                or_(
                    Program.updated_at > since,
                    Program.deleted_at > since,
                )
            )

        programs: list[Program] = list(db.execute(stmt).scalars().all())
        if not programs:
            return iter([])

        program_ids = [p.id for p in programs]

        accounts_by_prog = self._load_account_links(db, program_ids)
        investors_by_prog = self._load_investor_links(db, program_ids)
        suppliers_by_prog = self._load_supplier_links(db, program_ids)
        activities_by_prog = self._load_activities(db, program_ids)
        recent_by_prog = self._load_recent(db, program_ids)

        bundles: list[_ProgramBundle] = []
        for p in programs:
            bundles.append(
                _ProgramBundle(
                    program=p,
                    accounts=accounts_by_prog.get(p.id, []),
                    investors=investors_by_prog.get(p.id, []),
                    suppliers=suppliers_by_prog.get(p.id, []),
                    activities=activities_by_prog.get(p.id, []),
                    recent=recent_by_prog.get(p.id, []),
                )
            )
        return iter(bundles)

    def query_ids(self, db: Session) -> Iterable[int]:
        return db.execute(select(Program.id)).scalars()

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, row: _ProgramBundle, ctx: RenderContext) -> NoteDoc:
        bundle = row
        program = bundle.program

        title = (program.name or "").strip() or f"Untitled program {program.id}"
        stage = (program.stage or "unknown").strip() or "unknown"

        # Primary account link (frontmatter + body header convenience).
        account_link: Optional[str] = None
        if program.account is not None:
            account_name = (program.account.name or "").strip() or (
                f"account-{program.account_id}"
            )
            account_link = (
                f"[[account-{program.account_id}|{_wiki_display(account_name)}]]"
            )
        elif program.account_id:
            # Account row missing/soft-deleted but FK still set.
            account_link = (
                f"[[account-{program.account_id}|account-{program.account_id}]]"
            )

        path = f"{_FOLDER}/{_PREFIX}-{program.id}.md"

        frontmatter: dict[str, Any] = {
            "bifrost_id": program.id,
            "bifrost_type": _ENTITY_TYPE,
            "schema_version": ctx.schema_version,
            "title": title,
            "aliases": [title],
            # Programs have no separate ``status`` column; lifecycle is
            # tracked by ``stage``. Use a fixed status so the tagging
            # surface stays uniform with other entity types.
            "status": "active",
            "created_at": program.created_at,
            "updated_at": program.updated_at,
            "source": "bifrost",
            "tags": [
                f"bifrost/{_ENTITY_TYPE}",
                f"bifrost/stage/{stage}",
            ],
            "account_id": program.account_id,
            "account": account_link,
            "stage": stage,
            "estimated_value": _decimal_to_float(program.estimated_value),
            "probability_score": program.probability_score,
            "strategic_value_score": program.strategic_value_score,
            "owner": (program.owner or "").strip() or None,
            "next_step": (program.next_step or "").strip() or None,
            "accounts_count": len(bundle.accounts),
            "investors_count": len(bundle.investors),
            "suppliers_count": len(bundle.suppliers),
        }

        body = _build_body(
            title=title,
            program=program,
            account_link=account_link,
            accounts=bundle.accounts,
            investors=bundle.investors,
            suppliers=bundle.suppliers,
            activities=bundle.activities,
            recent=bundle.recent,
        )

        return NoteDoc(
            path=path,
            frontmatter=frontmatter,
            body=body,
            content_hash="",
        )

    def parents(self, row: _ProgramBundle) -> list[ParentRef]:
        program = row.program
        refs: list[ParentRef] = []

        # Primary account (FK is nullable=False per the model).
        if isinstance(program.account_id, int):
            refs.append(
                ParentRef(entity_type="account", entity_id=program.account_id)
            )

        # Investor firms via program_investors.
        for firm, _relevance in row.investors:
            refs.append(
                ParentRef(entity_type="investor_firm", entity_id=firm.id)
            )

        # Suppliers via program_suppliers.
        for supplier, _role, _status in row.suppliers:
            refs.append(
                ParentRef(entity_type="supplier", entity_id=supplier.id)
            )

        return refs

    # ------------------------------------------------------------------
    # batch loaders
    # ------------------------------------------------------------------

    @staticmethod
    def _load_account_links(
        db: Session, program_ids: list[int]
    ) -> dict[int, list[tuple[Account, str]]]:
        out: dict[int, list[tuple[Account, str]]] = defaultdict(list)
        if not program_ids:
            return out
        stmt = (
            select(ProgramAccount.program_id, Account, ProgramAccount.role)
            .join(Account, Account.id == ProgramAccount.account_id)
            .where(ProgramAccount.program_id.in_(program_ids))
            .where(Account.deleted_at.is_(None))
            .order_by(ProgramAccount.id)
        )
        for prog_id, account, role in db.execute(stmt).all():
            out[prog_id].append((account, role or ""))
        return out

    @staticmethod
    def _load_investor_links(
        db: Session, program_ids: list[int]
    ) -> dict[int, list[tuple[InvestorFirm, str]]]:
        out: dict[int, list[tuple[InvestorFirm, str]]] = defaultdict(list)
        if not program_ids:
            return out
        stmt = (
            select(
                ProgramInvestor.program_id,
                InvestorFirm,
                ProgramInvestor.relevance_type,
            )
            .join(InvestorFirm, InvestorFirm.id == ProgramInvestor.investor_id)
            .where(ProgramInvestor.program_id.in_(program_ids))
            .where(InvestorFirm.deleted_at.is_(None))
            .order_by(ProgramInvestor.id)
        )
        for prog_id, firm, relevance in db.execute(stmt).all():
            out[prog_id].append((firm, relevance or ""))
        return out

    @staticmethod
    def _load_supplier_links(
        db: Session, program_ids: list[int]
    ) -> dict[int, list[tuple[Supplier, str, str]]]:
        out: dict[int, list[tuple[Supplier, str, str]]] = defaultdict(list)
        if not program_ids:
            return out
        stmt = (
            select(
                ProgramSupplier.program_id,
                Supplier,
                ProgramSupplier.role,
                ProgramSupplier.status,
            )
            .join(Supplier, Supplier.id == ProgramSupplier.supplier_id)
            .where(ProgramSupplier.program_id.in_(program_ids))
            .where(Supplier.deleted_at.is_(None))
            .order_by(ProgramSupplier.id)
        )
        for prog_id, supplier, role, status in db.execute(stmt).all():
            out[prog_id].append((supplier, role or "", status or ""))
        return out

    @staticmethod
    def _load_activities(
        db: Session, program_ids: list[int]
    ) -> dict[int, list[ProgramActivity]]:
        out: dict[int, list[ProgramActivity]] = defaultdict(list)
        if not program_ids:
            return out
        # Newest first; secondary by id for stability when timestamps tie.
        stmt = (
            select(ProgramActivity)
            .where(ProgramActivity.program_id.in_(program_ids))
            .order_by(
                ProgramActivity.created_at.desc(),
                ProgramActivity.id.desc(),
            )
        )
        for activity in db.execute(stmt).scalars().all():
            out[activity.program_id].append(activity)
        return out

    @classmethod
    def _load_recent(
        cls, db: Session, program_ids: list[int]
    ) -> dict[int, list[_RecentItem]]:
        out: dict[int, list[_RecentItem]] = defaultdict(list)
        if not program_ids:
            return out

        # Meetings.
        m_stmt = select(Meeting).where(
            Meeting.entity_type == _ENTITY_TYPE,
            Meeting.entity_id.in_(program_ids),
            Meeting.deleted_at.is_(None),
        )
        for m in db.execute(m_stmt).scalars().all():
            out[m.entity_id].append(
                _RecentItem(
                    kind="meeting",
                    id=m.id,
                    display=(m.title or "").strip() or f"meeting-{m.id}",
                    when=m.starts_at or m.created_at,
                )
            )

        # Communications — column-select to bypass the optional
        # provenance columns (DB drift on source_system).
        c_stmt = select(
            Communication.id,
            Communication.entity_id,
            Communication.subject,
            Communication.channel,
            Communication.direction,
            Communication.sent_at,
            Communication.created_at,
        ).where(
            Communication.entity_type == _ENTITY_TYPE,
            Communication.entity_id.in_(program_ids),
            Communication.deleted_at.is_(None),
        )
        for (
            c_id,
            c_entity_id,
            c_subject,
            c_channel,
            c_direction,
            c_sent_at,
            c_created_at,
        ) in db.execute(c_stmt).all():
            subject = (c_subject or "").strip()
            if subject:
                display = subject
            else:
                fallback = " ".join(
                    p
                    for p in (
                        (c_channel or "").strip(),
                        (c_direction or "").strip(),
                    )
                    if p
                )
                display = fallback or f"comm-{c_id}"
            out[c_entity_id].append(
                _RecentItem(
                    kind="comm",
                    id=c_id,
                    display=display,
                    when=c_sent_at or c_created_at,
                )
            )

        # Notes — display string is constructed at render time so the
        # program name is consistent with the bundle's title.
        n_stmt = select(Note).where(
            Note.entity_type == _ENTITY_TYPE,
            Note.entity_id.in_(program_ids),
            Note.deleted_at.is_(None),
        )
        for n in db.execute(n_stmt).scalars().all():
            out[n.entity_id].append(
                _RecentItem(
                    kind="note",
                    id=n.id,
                    display="",
                    when=n.created_at,
                )
            )

        # Deterministic ordering: when DESC, then kind ASC, id ASC,
        # via two stable passes. Cap to the configured limit.
        for pid, items in out.items():
            items.sort(key=lambda x: (x.kind, x.id))
            items.sort(key=lambda x: x.when or _MIN_DT, reverse=True)
            out[pid] = items[:_ACTIVITY_LIMIT]
        return out


# ----------------------------------------------------------------------
# body assembly
# ----------------------------------------------------------------------


def _build_body(
    *,
    title: str,
    program: Program,
    account_link: Optional[str],
    accounts: list[tuple[Account, str]],
    investors: list[tuple[InvestorFirm, str]],
    suppliers: list[tuple[Supplier, str, str]],
    activities: list[ProgramActivity],
    recent: list[_RecentItem],
) -> str:
    stage_text = (program.stage or "—").strip() or "—"
    owner_text = (program.owner or "—").strip() or "—"
    value_text = _format_amount(program.estimated_value)
    prob_text = _format_score(program.probability_score)
    strategic_text = _format_score(program.strategic_value_score)
    next_step_text = (program.next_step or "—").strip() or "—"

    description = (
        _normalize_text(program.description) if program.description else "_(none)_"
    )

    parts = [
        f"# {_escape_inline(title)}",
        "",
        "## Status",
        "",
        f"- Stage: {_escape_inline(stage_text)}",
        f"- Owner: {_escape_inline(owner_text)}",
        f"- Value: {_escape_inline(value_text)}",
        f"- Probability: {_escape_inline(prob_text)}",
        f"- Strategic Value: {_escape_inline(strategic_text)}",
        f"- Next Step: {_escape_inline(next_step_text)}",
    ]
    if account_link is not None:
        parts.append(f"- Account: {account_link}")
    parts.extend(
        [
            "",
            "## Description",
            "",
            description,
            "",
            "## Accounts",
            "",
            _render_accounts(accounts),
            "",
            "## Investors",
            "",
            _render_investors(investors),
            "",
            "## Suppliers",
            "",
            _render_suppliers(suppliers),
            "",
            "## Activity Log",
            "",
            _render_activity_log(activities),
            "",
            "## Recent Communications & Meetings",
            "",
            _render_recent(recent, parent_label=title),
            "",
            "## Provenance",
            "",
            f"- bifrost_id: {program.id}",
            "- source: bifrost",
            "",
        ]
    )
    return "\n".join(parts)


def _render_accounts(accounts: list[tuple[Account, str]]) -> str:
    if not accounts:
        return "_(none)_"
    lines: list[str] = []
    for account, role in accounts:
        name = (account.name or "").strip() or f"account-{account.id}"
        role_text = role.strip() or "—"
        lines.append(
            f"- [[account-{account.id}|{_wiki_display(name)}]] — role: "
            f"{_escape_inline(role_text)}"
        )
    return "\n".join(lines)


def _render_investors(investors: list[tuple[InvestorFirm, str]]) -> str:
    if not investors:
        return "_(none)_"
    lines: list[str] = []
    for firm, relevance in investors:
        name = (firm.name or "").strip() or f"firm-{firm.id}"
        rel_text = relevance.strip() or "—"
        lines.append(
            f"- [[firm-{firm.id}|{_wiki_display(name)}]] — relevance: "
            f"{_escape_inline(rel_text)}"
        )
    return "\n".join(lines)


def _render_suppliers(suppliers: list[tuple[Supplier, str, str]]) -> str:
    if not suppliers:
        return "_(none)_"
    lines: list[str] = []
    for supplier, role, status in suppliers:
        name = (supplier.name or "").strip() or f"supplier-{supplier.id}"
        role_text = role.strip() or "—"
        status_text = status.strip() or "—"
        lines.append(
            f"- [[supplier-{supplier.id}|{_wiki_display(name)}]] — "
            f"role: {_escape_inline(role_text)}, "
            f"status: {_escape_inline(status_text)}"
        )
    return "\n".join(lines)


def _render_activity_log(activities: list[ProgramActivity]) -> str:
    if not activities:
        return "_(none)_"
    lines: list[str] = []
    for activity in activities:
        date_str = (
            activity.created_at.date().isoformat()
            if activity.created_at
            else "—"
        )
        kind = (activity.activity_type or "activity").strip() or "activity"
        description = (activity.description or "").strip()
        if description:
            lines.append(
                f"- {date_str} — {_escape_inline(kind)}: "
                f"{_escape_inline(description)}"
            )
        else:
            lines.append(f"- {date_str} — {_escape_inline(kind)}")
    return "\n".join(lines)


def _render_recent(items: list[_RecentItem], *, parent_label: str) -> str:
    if not items:
        return "_(none)_"
    lines: list[str] = []
    for item in items:
        date_str = item.when.date().isoformat() if item.when else "—"
        if item.kind == "note":
            target = f"note-{item.id}"
            display = f"Note on {parent_label}"
        elif item.kind == "meeting":
            target = f"meeting-{item.id}"
            display = item.display or target
        elif item.kind == "comm":
            target = f"comm-{item.id}"
            display = item.display or target
        else:
            continue
        lines.append(
            f"- {date_str} — [[{target}|{_wiki_display(display)}]]"
        )
    return "\n".join(lines)


# ----------------------------------------------------------------------
# formatting helpers
# ----------------------------------------------------------------------


def _decimal_to_float(value: Any) -> Optional[float]:
    """Convert a Decimal/Numeric column to a JSON-friendly float for
    frontmatter. Precision loss at amounts under ~1e15 is irrelevant
    for display."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, ArithmeticError):
        return None


def _format_amount(value: Any) -> str:
    if value is None:
        return "—"
    try:
        d = Decimal(str(value))
    except (ValueError, ArithmeticError):
        return str(value)
    if d == d.to_integral_value():
        return f"{int(d):,}"
    return f"{d:,.2f}"


def _format_score(value: Any) -> str:
    if value is None:
        return "—"
    return str(value)


def _wiki_display(text: str) -> str:
    return (
        text.replace("|", "/")
        .replace("]]", "] ]")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def _normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _escape_inline(value: str) -> str:
    return "".join(ch for ch in value if ch >= " " or ch == "\t").replace(
        "\t", " "
    )
