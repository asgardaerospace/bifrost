"""Transformer for ``investor_firms`` rows.

Produces one note per firm at
``Bifrost/Investors/Firms/firm-{id}.md`` with the rich body sections:
Summary, Contacts, Opportunities, Programs, Recent Activity.

Performance contract:
    * One main query for firms (with ``selectinload`` for contacts and
      opportunities — two extra IN-list queries, not N+1).
    * One query for programs joined through ``program_investors``.
    * One query per polymorphic activity table (meetings, communications,
      notes), each filtered with ``IN`` over the batch's firm and
      opportunity ids. Total: ~6 queries regardless of batch size.
    * Per-firm Python-side sorting of activity is O(k log k) on the
      pre-trimmed list — bounded by the configured limit.

Render is pure: the bundle returned by ``query_changed`` carries every
piece of data the body needs, so ``render`` never touches the DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Iterator, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.exporters.obsidian.types import NoteDoc, ParentRef, RenderContext
from app.models.communication import Communication
from app.models.investor import (
    InvestorContact,
    InvestorFirm,
    InvestorOpportunity,
)
from app.models.meeting import Meeting
from app.models.note import Note
from app.models.program import Program, ProgramInvestor


_ENTITY_TYPE = "investor_firm"
_PREFIX = "firm"
_FOLDER = "Bifrost/Investors/Firms"
_ACTIVITY_LIMIT = 10
_OPPORTUNITY_ENTITY_TYPE = "investor_opportunity"
_MIN_DT = datetime.min.replace(tzinfo=timezone.utc)


# ----------------------------------------------------------------------
# bundles passed from query → render
# ----------------------------------------------------------------------


@dataclass(slots=True)
class _ActivityItem:
    kind: str  # "meeting" | "comm" | "note"
    id: int
    display: str
    when: Optional[datetime]


@dataclass(slots=True)
class _FirmBundle:
    """All data needed to render one firm note.

    Exposes ``id`` and ``deleted_at`` as properties so the coordinator's
    ``getattr(row, ...)`` calls work without a custom Row protocol.
    """

    firm: InvestorFirm
    contacts: list[InvestorContact]
    opportunities: list[InvestorOpportunity]
    programs: list[tuple[Program, str]]
    activity: list[_ActivityItem]

    @property
    def id(self) -> int:
        return self.firm.id

    @property
    def deleted_at(self) -> Optional[datetime]:
        return self.firm.deleted_at


# ----------------------------------------------------------------------
# transformer
# ----------------------------------------------------------------------


class InvestorFirmTransformer:
    entity_type: str = _ENTITY_TYPE
    prefix: str = _PREFIX

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def query_changed(
        self, db: Session, since: datetime | None
    ) -> Iterable[_FirmBundle]:
        firm_stmt = (
            select(InvestorFirm)
            .options(
                selectinload(InvestorFirm.contacts),
                selectinload(InvestorFirm.opportunities),
            )
            .order_by(InvestorFirm.id)
        )
        if since is not None:
            firm_stmt = firm_stmt.where(
                or_(
                    InvestorFirm.updated_at > since,
                    InvestorFirm.deleted_at > since,
                )
            )

        firms: list[InvestorFirm] = list(db.execute(firm_stmt).scalars().all())
        if not firms:
            return iter([])

        firm_ids = [f.id for f in firms]

        # Map opportunity id → owning firm id, for routing polymorphic
        # activity that's attached at the opportunity level.
        opp_to_firm: dict[int, int] = {}
        for firm in firms:
            for opp in firm.opportunities:
                if opp.deleted_at is None:
                    opp_to_firm[opp.id] = firm.id

        programs_by_firm = self._load_programs(db, firm_ids)
        activity_by_firm = self._load_activity(
            db, firm_ids=firm_ids, opp_to_firm=opp_to_firm
        )

        return iter(self._build_bundles(
            firms=firms,
            programs_by_firm=programs_by_firm,
            activity_by_firm=activity_by_firm,
        ))

    def query_ids(self, db: Session) -> Iterable[int]:
        return db.execute(select(InvestorFirm.id)).scalars()

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, row: _FirmBundle, ctx: RenderContext) -> NoteDoc:
        bundle = row
        firm = bundle.firm
        title = (firm.name or "").strip() or f"Untitled investor_firm {firm.id}"
        status = (firm.status or "unknown").strip() or "unknown"

        path = f"{_FOLDER}/{_PREFIX}-{firm.id}.md"

        frontmatter: dict[str, Any] = {
            "bifrost_id": firm.id,
            "bifrost_type": _ENTITY_TYPE,
            "schema_version": ctx.schema_version,
            "title": title,
            "aliases": [title],
            "status": status,
            "created_at": firm.created_at,
            "updated_at": firm.updated_at,
            "source": "bifrost",
            "tags": [
                f"bifrost/{_ENTITY_TYPE}",
                f"bifrost/status/{status}",
            ],
            "website": firm.website,
            "stage_focus": firm.stage_focus,
            "location": firm.location,
            "contacts_count": len(bundle.contacts),
            "opportunities_count": len(bundle.opportunities),
            "programs_count": len(bundle.programs),
        }

        body = _build_body(
            title=title,
            firm=firm,
            contacts=bundle.contacts,
            opportunities=bundle.opportunities,
            programs=bundle.programs,
            activity=bundle.activity,
        )

        return NoteDoc(
            path=path,
            frontmatter=frontmatter,
            body=body,
            content_hash="",
        )

    def parents(self, row: _FirmBundle) -> list[ParentRef]:
        return []

    # ------------------------------------------------------------------
    # batch loaders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_bundles(
        *,
        firms: list[InvestorFirm],
        programs_by_firm: dict[int, list[tuple[Program, str]]],
        activity_by_firm: dict[int, list[_ActivityItem]],
    ) -> list[_FirmBundle]:
        bundles: list[_FirmBundle] = []
        for firm in firms:
            contacts = sorted(
                [c for c in firm.contacts if c.deleted_at is None],
                key=lambda c: c.id,
            )
            opportunities = sorted(
                [o for o in firm.opportunities if o.deleted_at is None],
                key=lambda o: o.id,
            )
            bundles.append(
                _FirmBundle(
                    firm=firm,
                    contacts=contacts,
                    opportunities=opportunities,
                    programs=programs_by_firm.get(firm.id, []),
                    activity=activity_by_firm.get(firm.id, []),
                )
            )
        return bundles

    @staticmethod
    def _load_programs(
        db: Session, firm_ids: list[int]
    ) -> dict[int, list[tuple[Program, str]]]:
        out: dict[int, list[tuple[Program, str]]] = {fid: [] for fid in firm_ids}
        if not firm_ids:
            return out

        stmt = (
            select(
                Program,
                ProgramInvestor.investor_id,
                ProgramInvestor.relevance_type,
            )
            .join(ProgramInvestor, ProgramInvestor.program_id == Program.id)
            .where(ProgramInvestor.investor_id.in_(firm_ids))
            .where(Program.deleted_at.is_(None))
            .order_by(Program.id)
        )
        for program, investor_id, relevance_type in db.execute(stmt).all():
            out[investor_id].append((program, relevance_type or ""))
        return out

    @classmethod
    def _load_activity(
        cls,
        db: Session,
        *,
        firm_ids: list[int],
        opp_to_firm: dict[int, int],
    ) -> dict[int, list[_ActivityItem]]:
        out: dict[int, list[_ActivityItem]] = {fid: [] for fid in firm_ids}
        opp_ids = list(opp_to_firm.keys())
        if not firm_ids:
            return out

        # Each polymorphic table is queried once with a combined
        # predicate: direct firm-attached rows OR rows attached to one
        # of this batch's opportunities. ``firm_ids`` is always non-empty
        # at this point; ``opp_ids`` may be empty.
        def _route(entity_type: str, entity_id: int) -> Optional[int]:
            if entity_type == _ENTITY_TYPE:
                return entity_id if entity_id in out else None
            if entity_type == _OPPORTUNITY_ENTITY_TYPE:
                return opp_to_firm.get(entity_id)
            return None

        # Meetings.
        m_stmt = select(Meeting).where(
            cls._activity_predicate(
                Meeting.entity_type, Meeting.entity_id, firm_ids, opp_ids
            ),
            Meeting.deleted_at.is_(None),
        )
        for m in db.execute(m_stmt).scalars().all():
            firm_id = _route(m.entity_type, m.entity_id)
            if firm_id is None:
                continue
            display = (m.title or "").strip() or f"meeting-{m.id}"
            out[firm_id].append(
                _ActivityItem(
                    kind="meeting",
                    id=m.id,
                    display=display,
                    when=m.starts_at or m.created_at,
                )
            )

        # Communications. We select only the columns we need rather
        # than the full ORM object — keeps the query independent of
        # schema-drift on optional provenance columns.
        c_stmt = select(
            Communication.id,
            Communication.entity_type,
            Communication.entity_id,
            Communication.subject,
            Communication.channel,
            Communication.direction,
            Communication.sent_at,
            Communication.created_at,
        ).where(
            cls._activity_predicate(
                Communication.entity_type, Communication.entity_id, firm_ids, opp_ids
            ),
            Communication.deleted_at.is_(None),
        )
        for (
            c_id,
            c_entity_type,
            c_entity_id,
            c_subject,
            c_channel,
            c_direction,
            c_sent_at,
            c_created_at,
        ) in db.execute(c_stmt).all():
            firm_id = _route(c_entity_type, c_entity_id)
            if firm_id is None:
                continue
            subject = (c_subject or "").strip()
            if subject:
                display = subject
            else:
                fallback = " ".join(
                    p for p in ((c_channel or "").strip(), (c_direction or "").strip()) if p
                )
                display = fallback or f"comm-{c_id}"
            out[firm_id].append(
                _ActivityItem(
                    kind="comm",
                    id=c_id,
                    display=display,
                    when=c_sent_at or c_created_at,
                )
            )

        # Notes — display string is constructed at render time so the
        # firm name is consistent with whatever the bundle uses.
        n_stmt = select(Note).where(
            cls._activity_predicate(
                Note.entity_type, Note.entity_id, firm_ids, opp_ids
            ),
            Note.deleted_at.is_(None),
        )
        for n in db.execute(n_stmt).scalars().all():
            firm_id = _route(n.entity_type, n.entity_id)
            if firm_id is None:
                continue
            out[firm_id].append(
                _ActivityItem(
                    kind="note",
                    id=n.id,
                    display="",  # filled in by _render_activity
                    when=n.created_at,
                )
            )

        # Deterministic ordering: when DESC, then kind ASC, then id ASC.
        # Python's sort is stable, so two passes give us that ordering.
        for fid, items in out.items():
            items.sort(key=lambda x: (x.kind, x.id))
            items.sort(key=lambda x: x.when or _MIN_DT, reverse=True)
            out[fid] = items[:_ACTIVITY_LIMIT]
        return out

    @staticmethod
    def _activity_predicate(
        entity_type_col,
        entity_id_col,
        firm_ids: list[int],
        opp_ids: list[int],
    ):
        """Build ``(type='investor_firm' AND id IN firms) OR (type='opp' AND id IN opps)``.

        Both branches are emitted only when their id list is non-empty
        so we never produce an ``IN ()`` (which Postgres rejects).
        """
        clauses = []
        if firm_ids:
            clauses.append(
                and_(
                    entity_type_col == _ENTITY_TYPE,
                    entity_id_col.in_(firm_ids),
                )
            )
        if opp_ids:
            clauses.append(
                and_(
                    entity_type_col == _OPPORTUNITY_ENTITY_TYPE,
                    entity_id_col.in_(opp_ids),
                )
            )
        return or_(*clauses) if clauses else False  # noqa: E712


# ----------------------------------------------------------------------
# body assembly
# ----------------------------------------------------------------------


def _build_body(
    *,
    title: str,
    firm: InvestorFirm,
    contacts: list[InvestorContact],
    opportunities: list[InvestorOpportunity],
    programs: list[tuple[Program, str]],
    activity: list[_ActivityItem],
) -> str:
    summary = (
        _normalize_text(firm.description) if firm.description else "_(none)_"
    )
    parts = [
        f"# {_escape_inline(title)}",
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Contacts",
        "",
        _render_contacts(contacts),
        "",
        "## Opportunities",
        "",
        _render_opportunities(opportunities),
        "",
        "## Programs",
        "",
        _render_programs(programs),
        "",
        "## Recent Activity",
        "",
        _render_activity(activity, firm_name=title),
        "",
    ]
    return "\n".join(parts)


def _render_contacts(contacts: list[InvestorContact]) -> str:
    if not contacts:
        return "_(none)_"
    lines: list[str] = []
    for c in contacts:
        name = (c.name or "").strip() or f"contact-{c.id}"
        title = (c.title or "").strip()
        link = f"[[contact-{c.id}|{_wiki_display(name)}]]"
        if title:
            lines.append(f"- {link} — {_escape_inline(title)}")
        else:
            lines.append(f"- {link}")
    return "\n".join(lines)


def _render_opportunities(opportunities: list[InvestorOpportunity]) -> str:
    if not opportunities:
        return "_(none)_"
    lines = [
        "| Stage | Amount | Target Close | Next Step |",
        "|---|---|---|---|",
    ]
    for o in opportunities:
        stage = (o.stage or "").strip() or "—"
        amount = _format_amount(o.amount)
        target = (
            o.target_close_date.isoformat() if o.target_close_date else "—"
        )
        next_step = (o.next_step or "").strip() or "—"
        lines.append(
            "| "
            + " | ".join(
                _cell(v) for v in (stage, amount, target, next_step)
            )
            + " |"
        )
    return "\n".join(lines)


def _render_programs(programs: list[tuple[Program, str]]) -> str:
    if not programs:
        return "_(none)_"
    lines: list[str] = []
    for program, relevance in programs:
        name = (program.name or "").strip() or f"program-{program.id}"
        rel = (relevance or "").strip() or "—"
        lines.append(
            f"- [[program-{program.id}|{_wiki_display(name)}]] — relevance: "
            f"{_escape_inline(rel)}"
        )
    return "\n".join(lines)


def _render_activity(items: list[_ActivityItem], *, firm_name: str) -> str:
    if not items:
        return "_(none)_"
    lines: list[str] = []
    for item in items:
        date_str = item.when.date().isoformat() if item.when else "—"
        if item.kind == "note":
            target = f"note-{item.id}"
            display = f"Note on {firm_name}"
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


def _format_amount(amount: Any) -> str:
    if amount is None:
        return "—"
    try:
        d = Decimal(str(amount))
    except (ValueError, ArithmeticError):
        return str(amount)
    if d == d.to_integral_value():
        return f"{int(d):,}"
    return f"{d:,.2f}"


def _cell(text: str) -> str:
    # Markdown table cells: escape pipes, collapse newlines.
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _wiki_display(text: str) -> str:
    # Wikilink display segment: pipes split target/display, ``]]`` ends
    # the link. Replace both so user-typed text can't break the link.
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
