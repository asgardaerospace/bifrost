"""Transformer for ``meetings`` rows.

Meetings are polymorphic, like notes. They render at
``Bifrost/Meetings/{YYYY}/{MM}/meeting-{id}.md`` — date-sharded by
``starts_at`` when present, falling back to ``created_at``.

Parent resolution and reverse-touch ParentRef behavior mirror the
note transformer: only types with a registered transformer get a
wikilink + ParentRef; everything else falls back to plain text and
emits no parent ref.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.exporters.obsidian.types import NoteDoc, ParentRef, RenderContext
from app.models.investor import InvestorContact, InvestorFirm
from app.models.market import Account
from app.models.meeting import Meeting
from app.models.program import Program
from app.models.supplier import Supplier


_ENTITY_TYPE = "meeting"
_PREFIX = "meeting"
_FOLDER = "Bifrost/Meetings"


# ----------------------------------------------------------------------
# parent registry — must stay in sync with note.py and the type→prefix
# map elsewhere. When this set of supported types grows, both
# transformers should be updated together.
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
# bundles
# ----------------------------------------------------------------------


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
class _MeetingBundle:
    meeting: Meeting
    parent: _ParentInfo

    @property
    def id(self) -> int:
        return self.meeting.id

    @property
    def deleted_at(self) -> Optional[datetime]:
        return self.meeting.deleted_at


# ----------------------------------------------------------------------
# transformer
# ----------------------------------------------------------------------


class MeetingTransformer:
    entity_type: str = _ENTITY_TYPE
    prefix: str = _PREFIX

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def query_changed(
        self, db: Session, since: datetime | None
    ) -> Iterable[_MeetingBundle]:
        stmt = select(Meeting).order_by(Meeting.id)
        if since is not None:
            stmt = stmt.where(
                or_(
                    Meeting.updated_at > since,
                    Meeting.deleted_at > since,
                )
            )
        stmt = stmt.execution_options(yield_per=500)

        meetings: list[Meeting] = list(db.execute(stmt).scalars().all())
        if not meetings:
            return iter([])

        title_map = self._resolve_parent_titles(db, meetings)

        bundles: list[_MeetingBundle] = []
        for m in meetings:
            spec = _PARENT_SPECS.get(m.entity_type)
            title = title_map.get((m.entity_type, m.entity_id))
            bundles.append(
                _MeetingBundle(
                    meeting=m,
                    parent=_ParentInfo(
                        entity_type=m.entity_type,
                        entity_id=m.entity_id,
                        spec=spec,
                        title=title,
                    ),
                )
            )
        return iter(bundles)

    def query_ids(self, db: Session) -> Iterable[int]:
        return db.execute(select(Meeting.id)).scalars()

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, row: _MeetingBundle, ctx: RenderContext) -> NoteDoc:
        bundle = row
        meeting = bundle.meeting
        parent = bundle.parent

        title = (meeting.title or "").strip() or f"meeting-{meeting.id}"
        location = (meeting.location or "").strip()

        path = _shard_path(
            meeting.id, meeting.starts_at, meeting.created_at
        )

        parent_link: Optional[str] = None
        if parent.supported and parent.prefix is not None:
            display = parent.title or f"{parent.prefix}-{parent.entity_id}"
            parent_link = (
                f"[[{parent.prefix}-{parent.entity_id}|{_wiki_display(display)}]]"
            )

        tags = [
            f"bifrost/{_ENTITY_TYPE}",
            "bifrost/status/active",
            f"bifrost/parent/{parent.entity_type}",
        ]

        frontmatter: dict[str, Any] = {
            "bifrost_id": meeting.id,
            "bifrost_type": _ENTITY_TYPE,
            "schema_version": ctx.schema_version,
            "title": title,
            "aliases": [title],
            "status": "active",
            "created_at": meeting.created_at,
            "updated_at": meeting.updated_at,
            "source": "bifrost",
            "tags": tags,
            "parent_type": parent.entity_type,
            "parent_id": parent.entity_id,
            "parent": parent_link,
            "starts_at": meeting.starts_at,
            "ends_at": meeting.ends_at,
            "location": location or None,
            "outcome_summary": (meeting.outcome or "").strip() or None,
        }

        body = _build_body(
            meeting_id=meeting.id,
            title=title,
            starts_at=meeting.starts_at,
            ends_at=meeting.ends_at,
            location=location,
            parent=parent,
            outcome=meeting.outcome,
            next_step=meeting.next_step,
            raw_notes=meeting.raw_notes,
        )

        return NoteDoc(
            path=path,
            frontmatter=frontmatter,
            body=body,
            content_hash="",
        )

    def parents(self, row: _MeetingBundle) -> list[ParentRef]:
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
        db: Session, meetings: list[Meeting]
    ) -> dict[tuple[str, int], str]:
        ids_by_type: dict[str, set[int]] = defaultdict(set)
        for m in meetings:
            ids_by_type[m.entity_type].add(m.entity_id)

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
# body assembly
# ----------------------------------------------------------------------


def _build_body(
    *,
    meeting_id: int,
    title: str,
    starts_at: Optional[datetime],
    ends_at: Optional[datetime],
    location: str,
    parent: _ParentInfo,
    outcome: Optional[str],
    next_step: Optional[str],
    raw_notes: Optional[str],
) -> str:
    starts_text = _isoformat(starts_at) if starts_at else "—"
    ends_text = _isoformat(ends_at) if ends_at else "—"
    location_text = _escape_inline(location) if location else "—"

    parent_line = _render_parent_line(parent)

    outcome_block = (
        _normalize_text(outcome) if outcome and outcome.strip() else "_(none)_"
    )
    next_step_block = (
        _normalize_text(next_step)
        if next_step and next_step.strip()
        else "_(none)_"
    )
    raw_notes_block = (
        _normalize_text(raw_notes)
        if raw_notes and raw_notes.strip()
        else "_(none)_"
    )

    parts = [
        f"# {_escape_inline(title)}",
        "",
        "## When & Where",
        "",
        f"- Starts: {starts_text}",
        f"- Ends: {ends_text}",
        f"- Location: {location_text}",
        "",
        "## Parent",
        "",
        parent_line,
        "",
        "## Outcome",
        "",
        outcome_block,
        "",
        "## Next Step",
        "",
        next_step_block,
        "",
        "## Raw Notes",
        "",
        raw_notes_block,
        "",
        "## Provenance",
        "",
        f"- bifrost_id: {meeting_id}",
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
    meeting_id: int,
    starts_at: Optional[datetime],
    created_at: Optional[datetime],
) -> str:
    when = starts_at or created_at
    if when is None:
        year, month = "0000", "00"
    else:
        year = f"{when.year:04d}"
        month = f"{when.month:02d}"
    return f"{_FOLDER}/{year}/{month}/{_PREFIX}-{meeting_id}.md"


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
