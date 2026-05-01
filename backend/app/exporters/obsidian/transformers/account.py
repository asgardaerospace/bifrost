"""Transformer for ``accounts`` rows.

Produces one note per account at
``Bifrost/Accounts/account-{id}.md``.

Performance contract for a batch of N accounts:
    * 1 main query for accounts (with selectinload on contacts)
    * 1 query for program_accounts joined to programs (Programs section)
    * 1 query each for meetings/communications/notes filtered with
      ``entity_type='account' AND entity_id IN (...)``

Parent refs are intentionally empty: an account is conceptually a
top-of-tree entity (programs are children of accounts, not the other
way around). Children that mark accounts dirty will trigger refresh
through the coordinator's existing reverse-touch path.

Account contacts are rendered inline as plain-text bullets rather
than wikilinks: there is no ``account_contact`` transformer yet, and
the canonical filename regex (``^[a-z]+-\\d+\\.md$``) precludes a
multi-hyphen prefix. When an AccountContact transformer is added
later (e.g. with prefix ``acctcontact``), the body renderer here
becomes a one-line swap.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.exporters.obsidian.types import NoteDoc, ParentRef, RenderContext
from app.models.communication import Communication
from app.models.market import Account, AccountContact
from app.models.meeting import Meeting
from app.models.note import Note
from app.models.program import Program, ProgramAccount


_ENTITY_TYPE = "account"
_PREFIX = "account"
_FOLDER = "Bifrost/Accounts"
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
class _AccountBundle:
    account: Account
    contacts: list[AccountContact]
    programs: list[tuple[Program, str]]  # (program, role from program_accounts)
    recent: list[_RecentItem]

    @property
    def id(self) -> int:
        return self.account.id

    @property
    def deleted_at(self) -> Optional[datetime]:
        return self.account.deleted_at


# ----------------------------------------------------------------------
# transformer
# ----------------------------------------------------------------------


class AccountTransformer:
    entity_type: str = _ENTITY_TYPE
    prefix: str = _PREFIX

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def query_changed(
        self, db: Session, since: datetime | None
    ) -> Iterable[_AccountBundle]:
        stmt = (
            select(Account)
            .options(selectinload(Account.contacts))
            .order_by(Account.id)
        )
        if since is not None:
            stmt = stmt.where(
                or_(
                    Account.updated_at > since,
                    Account.deleted_at > since,
                )
            )

        accounts: list[Account] = list(db.execute(stmt).scalars().all())
        if not accounts:
            return iter([])

        account_ids = [a.id for a in accounts]

        programs_by_account = self._load_programs(db, account_ids)
        recent_by_account = self._load_recent(db, account_ids)

        bundles: list[_AccountBundle] = []
        for a in accounts:
            contacts = sorted(
                [c for c in a.contacts if c.deleted_at is None],
                key=lambda c: c.id,
            )
            bundles.append(
                _AccountBundle(
                    account=a,
                    contacts=contacts,
                    programs=programs_by_account.get(a.id, []),
                    recent=recent_by_account.get(a.id, []),
                )
            )
        return iter(bundles)

    def query_ids(self, db: Session) -> Iterable[int]:
        return db.execute(select(Account.id)).scalars()

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, row: _AccountBundle, ctx: RenderContext) -> NoteDoc:
        bundle = row
        account = bundle.account

        title = (account.name or "").strip() or f"Untitled account {account.id}"
        sector = (account.sector or "").strip()
        region = (account.region or "").strip()
        account_type = (account.type or "").strip()
        website = (account.website or "").strip()

        # Accounts have no own status column; lifecycle is captured by
        # the coordinator via deleted_at. Use a fixed status for tag
        # symmetry with other entity types.
        status = "active"

        path = f"{_FOLDER}/{_PREFIX}-{account.id}.md"

        tags = [f"bifrost/{_ENTITY_TYPE}", f"bifrost/status/{status}"]
        if sector:
            tags.append(f"bifrost/sector/{sector}")

        frontmatter: dict[str, Any] = {
            "bifrost_id": account.id,
            "bifrost_type": _ENTITY_TYPE,
            "schema_version": ctx.schema_version,
            "title": title,
            "aliases": [title],
            "status": status,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
            "source": "bifrost",
            "tags": tags,
            "sector": sector or None,
            "region": region or None,
            "account_type": account_type or None,
            "website": website or None,
            "contacts_count": len(bundle.contacts),
            "programs_count": len(bundle.programs),
        }

        body = _build_body(
            account_id=account.id,
            title=title,
            description=account.notes,
            contacts=bundle.contacts,
            programs=bundle.programs,
            recent=bundle.recent,
        )

        return NoteDoc(
            path=path,
            frontmatter=frontmatter,
            body=body,
            content_hash="",
        )

    def parents(self, row: _AccountBundle) -> list[ParentRef]:
        return []

    # ------------------------------------------------------------------
    # batch loaders
    # ------------------------------------------------------------------

    @staticmethod
    def _load_programs(
        db: Session, account_ids: list[int]
    ) -> dict[int, list[tuple[Program, str]]]:
        out: dict[int, list[tuple[Program, str]]] = defaultdict(list)
        if not account_ids:
            return out
        stmt = (
            select(ProgramAccount.account_id, Program, ProgramAccount.role)
            .join(Program, Program.id == ProgramAccount.program_id)
            .where(ProgramAccount.account_id.in_(account_ids))
            .where(Program.deleted_at.is_(None))
            .order_by(Program.id)
        )
        for account_id, program, role in db.execute(stmt).all():
            out[account_id].append((program, role or ""))
        return out

    @classmethod
    def _load_recent(
        cls, db: Session, account_ids: list[int]
    ) -> dict[int, list[_RecentItem]]:
        out: dict[int, list[_RecentItem]] = defaultdict(list)
        if not account_ids:
            return out

        # Meetings.
        m_stmt = select(Meeting).where(
            Meeting.entity_type == _ENTITY_TYPE,
            Meeting.entity_id.in_(account_ids),
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
        # ``source_system`` columns (DB drift).
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
            Communication.entity_id.in_(account_ids),
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

        # Notes — display constructed at render time so the account
        # name in the bundle stays the source of truth.
        n_stmt = select(Note).where(
            Note.entity_type == _ENTITY_TYPE,
            Note.entity_id.in_(account_ids),
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
        # via two stable passes; capped at the configured limit.
        for aid, items in out.items():
            items.sort(key=lambda x: (x.kind, x.id))
            items.sort(key=lambda x: x.when or _MIN_DT, reverse=True)
            out[aid] = items[:_ACTIVITY_LIMIT]
        return out


# ----------------------------------------------------------------------
# body assembly
# ----------------------------------------------------------------------


def _build_body(
    *,
    account_id: int,
    title: str,
    description: Optional[str],
    contacts: list[AccountContact],
    programs: list[tuple[Program, str]],
    recent: list[_RecentItem],
) -> str:
    summary = (
        _normalize_text(description) if description else "_(none)_"
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
        "## Programs",
        "",
        _render_programs(programs),
        "",
        "## Recent Activity",
        "",
        _render_recent(recent, parent_label=title),
        "",
        "## Provenance",
        "",
        f"- bifrost_id: {account_id}",
        "- source: bifrost",
        "",
    ]
    return "\n".join(parts)


def _render_contacts(contacts: list[AccountContact]) -> str:
    if not contacts:
        return "_(none)_"
    lines: list[str] = []
    for c in contacts:
        # Plain-text rendering — see module docstring for rationale.
        name = (c.name or "").strip() or f"contact-{c.id}"
        title = (c.title or "").strip()
        if title:
            lines.append(
                f"- {_escape_inline(name)} — {_escape_inline(title)}"
            )
        else:
            lines.append(f"- {_escape_inline(name)}")
    return "\n".join(lines)


def _render_programs(programs: list[tuple[Program, str]]) -> str:
    if not programs:
        return "_(none)_"
    lines: list[str] = []
    for program, role in programs:
        name = (program.name or "").strip() or f"program-{program.id}"
        role_text = role.strip() or "—"
        lines.append(
            f"- [[program-{program.id}|{_wiki_display(name)}]] — role: "
            f"{_escape_inline(role_text)}"
        )
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
