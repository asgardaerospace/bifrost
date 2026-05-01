"""Transformer for ``communications`` rows.

Communications are polymorphic, like meetings and notes. They render
at ``Bifrost/Communications/{YYYY}/{MM}/comm-{id}.md`` — date-sharded
by ``sent_at`` when present, falling back to ``created_at``.

DB-drift workaround: the model declares ``source_system`` and
``source_external_id`` columns that don't exist in the live database
(pending migration). This transformer therefore never loads the full
ORM object — it column-selects only the fields the renderer uses.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.exporters.obsidian.types import NoteDoc, ParentRef, RenderContext
from app.models.communication import Communication
from app.models.investor import InvestorContact, InvestorFirm
from app.models.market import Account
from app.models.program import Program
from app.models.supplier import Supplier


_ENTITY_TYPE = "communication"
_PREFIX = "comm"
_FOLDER = "Bifrost/Communications"


# ----------------------------------------------------------------------
# parent registry — keep in sync with note.py / meeting.py.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _ParentSpec:
    prefix: str
    model: type
    name_attr: str
    supported: bool


_PARENT_SPECS: dict[str, _ParentSpec] = {
    "investor_firm": _ParentSpec("firm", InvestorFirm, "name", True),
    "investor_contact": _ParentSpec("contact", InvestorContact, "name", True),
    "account": _ParentSpec("account", Account, "name", True),
    "program": _ParentSpec("program", Program, "name", True),
    "supplier": _ParentSpec("supplier", Supplier, "name", True),
}


# ----------------------------------------------------------------------
# row + bundle dataclasses
# ----------------------------------------------------------------------


@dataclass(slots=True)
class _CommRow:
    """Pure-data view of a single ``communications`` row, populated
    from a column-select. Avoids loading the full ORM object so we
    don't trip over the missing ``source_system`` columns."""

    id: int
    entity_type: str
    entity_id: int
    channel: Optional[str]
    direction: Optional[str]
    status: Optional[str]
    subject: Optional[str]
    body: Optional[str]
    from_address: Optional[str]
    to_address: Optional[str]
    sent_at: Optional[datetime]
    deleted_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@dataclass(slots=True)
class _ParentInfo:
    entity_type: str
    entity_id: int
    spec: Optional[_ParentSpec]
    title: Optional[str]

    @property
    def supported(self) -> bool:
        return self.spec is not None and self.spec.supported

    @property
    def prefix(self) -> Optional[str]:
        return self.spec.prefix if self.spec else None


@dataclass(slots=True)
class _CommBundle:
    comm: _CommRow
    parent: _ParentInfo

    @property
    def id(self) -> int:
        return self.comm.id

    @property
    def deleted_at(self) -> Optional[datetime]:
        return self.comm.deleted_at


# ----------------------------------------------------------------------
# transformer
# ----------------------------------------------------------------------


class CommunicationTransformer:
    entity_type: str = _ENTITY_TYPE
    prefix: str = _PREFIX

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def query_changed(
        self, db: Session, since: datetime | None
    ) -> Iterable[_CommBundle]:
        # Explicit column list — no full ORM load.
        stmt = select(
            Communication.id,
            Communication.entity_type,
            Communication.entity_id,
            Communication.channel,
            Communication.direction,
            Communication.status,
            Communication.subject,
            Communication.body,
            Communication.from_address,
            Communication.to_address,
            Communication.sent_at,
            Communication.deleted_at,
            Communication.created_at,
            Communication.updated_at,
        ).order_by(Communication.id)

        if since is not None:
            stmt = stmt.where(
                or_(
                    Communication.updated_at > since,
                    Communication.deleted_at > since,
                )
            )

        rows = db.execute(stmt).all()
        if not rows:
            return iter([])

        comms = [_CommRow(**row._mapping) for row in rows]
        title_map = self._resolve_parent_titles(db, comms)

        bundles: list[_CommBundle] = []
        for c in comms:
            spec = _PARENT_SPECS.get(c.entity_type)
            title = title_map.get((c.entity_type, c.entity_id))
            bundles.append(
                _CommBundle(
                    comm=c,
                    parent=_ParentInfo(
                        entity_type=c.entity_type,
                        entity_id=c.entity_id,
                        spec=spec,
                        title=title,
                    ),
                )
            )
        return iter(bundles)

    def query_ids(self, db: Session) -> Iterable[int]:
        return db.execute(select(Communication.id)).scalars()

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, row: _CommBundle, ctx: RenderContext) -> NoteDoc:
        bundle = row
        comm = bundle.comm
        parent = bundle.parent

        title = _build_title(comm)

        path = _shard_path(comm.id, comm.sent_at, comm.created_at)

        parent_link: Optional[str] = None
        if parent.supported and parent.prefix is not None:
            display = parent.title or f"{parent.prefix}-{parent.entity_id}"
            parent_link = (
                f"[[{parent.prefix}-{parent.entity_id}|{_wiki_display(display)}]]"
            )

        comm_status = (comm.status or "").strip()
        channel = (comm.channel or "").strip()
        direction = (comm.direction or "").strip()

        tags = [
            f"bifrost/{_ENTITY_TYPE}",
            f"bifrost/status/{comm_status or 'unknown'}",
            f"bifrost/parent/{parent.entity_type}",
        ]
        if channel:
            tags.append(f"bifrost/channel/{channel}")

        frontmatter: dict[str, Any] = {
            "bifrost_id": comm.id,
            "bifrost_type": _ENTITY_TYPE,
            "schema_version": ctx.schema_version,
            "title": title,
            "aliases": [title],
            "status": comm_status or "unknown",
            "created_at": comm.created_at,
            "updated_at": comm.updated_at,
            "source": "bifrost",
            "tags": tags,
            "parent_type": parent.entity_type,
            "parent_id": parent.entity_id,
            "parent": parent_link,
            "channel": channel or None,
            "direction": direction or None,
            "comm_status": comm_status or None,
            "subject": (comm.subject or "").strip() or None,
            "from_address": (comm.from_address or "").strip() or None,
            "to_address": (comm.to_address or "").strip() or None,
            "sent_at": comm.sent_at,
        }

        body = _build_body(
            comm_id=comm.id,
            title=title,
            comm=comm,
            parent=parent,
        )

        return NoteDoc(
            path=path,
            frontmatter=frontmatter,
            body=body,
            content_hash="",
        )

    def parents(self, row: _CommBundle) -> list[ParentRef]:
        parent = row.parent
        if not parent.supported:
            return []
        return [
            ParentRef(
                entity_type=parent.entity_type, entity_id=parent.entity_id
            )
        ]

    # ------------------------------------------------------------------
    # batch resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_parent_titles(
        db: Session, comms: list[_CommRow]
    ) -> dict[tuple[str, int], str]:
        ids_by_type: dict[str, set[int]] = defaultdict(set)
        for c in comms:
            ids_by_type[c.entity_type].add(c.entity_id)

        out: dict[tuple[str, int], str] = {}
        for entity_type, ids in ids_by_type.items():
            spec = _PARENT_SPECS.get(entity_type)
            if spec is None or not ids:
                continue
            id_col = getattr(spec.model, "id")
            name_col = getattr(spec.model, spec.name_attr)
            stmt = select(id_col, name_col).where(id_col.in_(list(ids)))
            for parent_id, parent_name in db.execute(stmt).all():
                out[(entity_type, parent_id)] = (parent_name or "").strip()
        return out


# ----------------------------------------------------------------------
# title + body assembly
# ----------------------------------------------------------------------


def _build_title(comm: _CommRow) -> str:
    subject = (comm.subject or "").strip()
    if subject:
        return subject
    parts = [
        s for s in ((comm.channel or "").strip(), (comm.direction or "").strip())
        if s
    ]
    if parts:
        return " ".join(parts)
    return f"comm-{comm.id}"


def _build_body(
    *,
    comm_id: int,
    title: str,
    comm: _CommRow,
    parent: _ParentInfo,
) -> str:
    from_text = _escape_inline((comm.from_address or "").strip()) or "—"
    to_text = _escape_inline((comm.to_address or "").strip()) or "—"
    channel_text = _escape_inline((comm.channel or "").strip()) or "—"
    direction_text = _escape_inline((comm.direction or "").strip()) or "—"
    sent_text = _isoformat(comm.sent_at) if comm.sent_at else "—"
    status_text = _escape_inline((comm.status or "").strip()) or "—"

    parent_line = _render_parent_line(parent)

    body_block = (
        _normalize_text(comm.body) if comm.body and comm.body.strip() else "_(none)_"
    )

    parts = [
        f"# {_escape_inline(title)}",
        "",
        "## Headers",
        "",
        f"- From: {from_text}",
        f"- To: {to_text}",
        f"- Channel: {channel_text}",
        f"- Direction: {direction_text}",
        f"- Sent: {sent_text}",
        f"- Status: {status_text}",
        "",
        "## Parent",
        "",
        parent_line,
        "",
        "## Body",
        "",
        body_block,
        "",
        "## Provenance",
        "",
        f"- bifrost_id: {comm_id}",
        "- source: bifrost",
        "",
    ]
    return "\n".join(parts)


def _render_parent_line(parent: _ParentInfo) -> str:
    if parent.supported and parent.prefix is not None:
        display = parent.title or f"{parent.prefix}-{parent.entity_id}"
        return (
            f"- [[{parent.prefix}-{parent.entity_id}|"
            f"{_wiki_display(display)}]] ({parent.entity_type})"
        )
    if parent.title:
        return (
            f"- {_escape_inline(parent.title)} "
            f"({parent.entity_type} {parent.entity_id})"
        )
    return f"- {parent.entity_type} {parent.entity_id} (unresolved)"


# ----------------------------------------------------------------------
# path sharding
# ----------------------------------------------------------------------


def _shard_path(
    comm_id: int,
    sent_at: Optional[datetime],
    created_at: Optional[datetime],
) -> str:
    when = sent_at or created_at
    if when is None:
        year, month = "0000", "00"
    else:
        year = f"{when.year:04d}"
        month = f"{when.month:02d}"
    return f"{_FOLDER}/{year}/{month}/{_PREFIX}-{comm_id}.md"


# ----------------------------------------------------------------------
# formatting helpers
# ----------------------------------------------------------------------


def _isoformat(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    s = dt.isoformat()
    return s[:-6] + "Z" if s.endswith("+00:00") else s


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
