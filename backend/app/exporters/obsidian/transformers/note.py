"""Transformer for ``notes`` rows.

Notes are polymorphic: each row attaches to a parent via the
``entity_type`` + ``entity_id`` pair. The transformer:

    * Renders one note per row at
      ``Bifrost/Notes/{YYYY}/{MM}/note-{id}.md`` (date-sharded by
      ``created_at`` to cap directory size as the table grows).
    * Resolves parent titles in batch from the supported-type tables.
    * Emits a wikilink to the parent only when its type has a
      registered transformer (i.e. a target file will exist in the
      vault). Other parent types render as plain text — the schema
      doc's "strict" orphan policy.
    * Returns a ``ParentRef`` only for supported parent types so
      reverse-touch refreshes the right parent without warning.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.exporters.obsidian.types import NoteDoc, ParentRef, RenderContext
from app.models.investor import InvestorContact, InvestorFirm
from app.models.market import Account
from app.models.note import Note
from app.models.program import Program
from app.models.supplier import Supplier


_ENTITY_TYPE = "note"
_PREFIX = "note"
_FOLDER = "Bifrost/Notes"


# ----------------------------------------------------------------------
# canonical parent registry
#
# Keep this in sync with the type→prefix map used by the other
# transformers and the wikilink builder. Each entry tells the note
# transformer:
#   * how to look up the parent's display title (model + name attr)
#   * what wikilink prefix to use
#   * whether the parent type is currently "supported" — i.e. has a
#     registered transformer that will produce a target file.
# Types not in this map render as plain text and yield no ParentRef.
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
    """Resolved view of a note's parent for rendering decisions."""

    entity_type: str
    entity_id: int
    spec: Optional[_ParentSpec]  # None if entity_type unsupported
    title: Optional[str]  # parent's display title; None if not in DB

    @property
    def supported(self) -> bool:
        return self.spec is not None and self.spec.supported

    @property
    def prefix(self) -> Optional[str]:
        return self.spec.prefix if self.spec else None


@dataclass(slots=True)
class _NoteBundle:
    note: Note
    parent: _ParentInfo

    @property
    def id(self) -> int:
        return self.note.id

    @property
    def deleted_at(self) -> Optional[datetime]:
        return self.note.deleted_at


# ----------------------------------------------------------------------
# transformer
# ----------------------------------------------------------------------


class NoteTransformer:
    entity_type: str = _ENTITY_TYPE
    prefix: str = _PREFIX

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def query_changed(
        self, db: Session, since: datetime | None
    ) -> Iterable[_NoteBundle]:
        stmt = select(Note).order_by(Note.id)
        if since is not None:
            stmt = stmt.where(
                or_(
                    Note.updated_at > since,
                    Note.deleted_at > since,
                )
            )
        stmt = stmt.execution_options(yield_per=500)

        notes: list[Note] = list(db.execute(stmt).scalars().all())
        if not notes:
            return iter([])

        title_map = self._resolve_parent_titles(db, notes)

        bundles: list[_NoteBundle] = []
        for n in notes:
            spec = _PARENT_SPECS.get(n.entity_type)
            title = title_map.get((n.entity_type, n.entity_id))
            bundles.append(
                _NoteBundle(
                    note=n,
                    parent=_ParentInfo(
                        entity_type=n.entity_type,
                        entity_id=n.entity_id,
                        spec=spec,
                        title=title,
                    ),
                )
            )
        return iter(bundles)

    def query_ids(self, db: Session) -> Iterable[int]:
        return db.execute(select(Note.id)).scalars()

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, row: _NoteBundle, ctx: RenderContext) -> NoteDoc:
        bundle = row
        note = bundle.note
        parent = bundle.parent

        parent_label = _resolve_parent_label(parent)
        title = f"Note on {parent_label}"
        author = (note.author or "").strip()

        path = _shard_path(note.id, note.created_at)

        # Frontmatter ``parent`` is the wikilink string only when the
        # parent type is supported AND we have something to display.
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
            "bifrost_id": note.id,
            "bifrost_type": _ENTITY_TYPE,
            "schema_version": ctx.schema_version,
            "title": title,
            "aliases": [title],
            "status": "active",
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "source": "bifrost",
            "tags": tags,
            "parent_type": parent.entity_type,
            "parent_id": parent.entity_id,
            "parent": parent_link,
            "author": author or None,
        }

        body = _build_body(
            note_id=note.id,
            parent_label=parent_label,
            parent=parent,
            note_body=note.body,
        )

        return NoteDoc(
            path=path,
            frontmatter=frontmatter,
            body=body,
            content_hash="",
        )

    def parents(self, row: _NoteBundle) -> list[ParentRef]:
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
        db: Session, notes: list[Note]
    ) -> dict[tuple[str, int], str]:
        """Look up parent display titles in batch, one query per
        supported type, ``IN``-list filtered.

        Returns a mapping ``(entity_type, entity_id) -> title``. Misses
        (unsupported types, deleted parents) simply don't appear in
        the dict — the renderer falls back to a generic label.
        """
        ids_by_type: dict[str, set[int]] = defaultdict(set)
        for n in notes:
            ids_by_type[n.entity_type].add(n.entity_id)

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
    note_id: int,
    parent_label: str,
    parent: _ParentInfo,
    note_body: Optional[str],
) -> str:
    parent_line = _render_parent_line(parent)
    body_text = _normalize_text(note_body) if note_body else ""
    body_block = body_text if body_text else "_(none)_"

    parts = [
        f"# Note on {_escape_inline(parent_label)}",
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
        f"- bifrost_id: {note_id}",
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


def _resolve_parent_label(parent: _ParentInfo) -> str:
    if parent.title:
        return parent.title
    if parent.spec is not None:
        return f"{parent.spec.prefix}-{parent.entity_id}"
    return f"{parent.entity_type} {parent.entity_id}"


# ----------------------------------------------------------------------
# path sharding
# ----------------------------------------------------------------------


def _shard_path(note_id: int, created_at: Optional[datetime]) -> str:
    if created_at is None:
        # Should not happen — TimestampMixin makes created_at NOT NULL —
        # but keep the path deterministic if it ever does.
        year, month = "0000", "00"
    else:
        year = f"{created_at.year:04d}"
        month = f"{created_at.month:02d}"
    return f"{_FOLDER}/{year}/{month}/{_PREFIX}-{note_id}.md"


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
