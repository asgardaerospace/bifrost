"""Transformer for ``intel_items`` rows (Intelligence OS).

Renders external news/market signals at
``Bifrost/Intel/{YYYY}/{MM}/intel-{id}.md`` — date-sharded by
``published_at`` when present, falling back to ``created_at``.

Intel items are top-of-tree from the exporter's perspective:
``parents()`` returns an empty list. Each item carries any number of
mentioned ``IntelEntity`` rows (which may or may not point to internal
records via ``entity_id``), free-form ``IntelTag`` rows, and a stream
of ``IntelAction`` rows holding recommended follow-ups.

Performance contract per N items:
    * 1 main query for ``intel_items`` (with selectinload on entities,
      tags, actions — three IN-list child queries)
    * 0–2 lookup queries for resolvable mentioned-entity wikilinks
      (only if the batch contains entries pointing at supported
      internal types)

Notable schema gaps that this transformer accommodates:
    * ``IntelItem`` has no ``deleted_at`` column — bundle's
      ``deleted_at`` property unconditionally returns ``None`` so the
      coordinator never tries to archive an intel note.
    * No ``intel_status`` column exists — surface a constant ``"new"``
      so Dataview consumers see a stable field. Move to a real DB
      column when one is added.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exporters.obsidian.types import NoteDoc, ParentRef, RenderContext
from app.models.intel import IntelAction, IntelEntity, IntelItem, IntelTag
from app.models.investor import InvestorFirm
from app.models.market import Account
from app.models.program import Program
from app.models.supplier import Supplier


_ENTITY_TYPE = "intel_item"
_PREFIX = "intel"
_FOLDER = "Bifrost/Intel"
_DEFAULT_INTEL_STATUS = "new"


# ----------------------------------------------------------------------
# intel-entity → internal-prefix map
#
# An IntelEntity row carries an ``entity_type`` from the
# Intelligence-OS vocabulary (``investor``, ``program``, ``company``,
# ``agency``, ``person``, ...) plus an optional ``entity_id`` pointer
# into one of our internal tables. Only types we have a registered
# transformer for AND that map cleanly to a single internal table get
# resolved into a wikilink. Everything else renders as plain text.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _IntelEntitySpec:
    prefix: str
    model: type
    name_attr: str


_INTEL_ENTITY_SPECS: dict[str, _IntelEntitySpec] = {
    "investor": _IntelEntitySpec("firm", InvestorFirm, "name"),
    "program": _IntelEntitySpec("program", Program, "name"),
    # ``company`` could be either an account or a supplier — ambiguous,
    # so we don't auto-resolve. Same story for ``agency`` (no internal
    # table). Both render as plain text.
}


# ----------------------------------------------------------------------
# bundle
# ----------------------------------------------------------------------


@dataclass(slots=True)
class _MentionedEntity:
    """One row from ``intel_entities``, augmented with a resolved
    title from the internal table when available."""

    intel_entity: IntelEntity
    spec: Optional[_IntelEntitySpec]
    resolved_title: Optional[str]


@dataclass(slots=True)
class _IntelBundle:
    intel: IntelItem
    entities: list[_MentionedEntity]
    intel_tags: list[IntelTag]
    actions: list[IntelAction]

    @property
    def id(self) -> int:
        return self.intel.id

    @property
    def deleted_at(self) -> Optional[datetime]:
        # IntelItem has no soft-delete column.
        return None


# ----------------------------------------------------------------------
# transformer
# ----------------------------------------------------------------------


class IntelItemTransformer:
    entity_type: str = _ENTITY_TYPE
    prefix: str = _PREFIX

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def query_changed(
        self, db: Session, since: datetime | None
    ) -> Iterable[_IntelBundle]:
        stmt = (
            select(IntelItem)
            .options(
                selectinload(IntelItem.entities),
                selectinload(IntelItem.tags),
                selectinload(IntelItem.actions),
            )
            .order_by(IntelItem.id)
        )
        if since is not None:
            stmt = stmt.where(IntelItem.updated_at > since)
        stmt = stmt.execution_options(yield_per=500)

        items: list[IntelItem] = list(db.execute(stmt).scalars().all())
        if not items:
            return iter([])

        title_map = self._resolve_mentioned_titles(db, items)

        bundles: list[_IntelBundle] = []
        for item in items:
            mentioned: list[_MentionedEntity] = []
            for ie in sorted(item.entities, key=lambda e: e.id):
                spec = _INTEL_ENTITY_SPECS.get(ie.entity_type)
                resolved_title = None
                if spec is not None and ie.entity_id is not None:
                    resolved_title = title_map.get(
                        (ie.entity_type, ie.entity_id)
                    )
                mentioned.append(
                    _MentionedEntity(
                        intel_entity=ie,
                        spec=spec,
                        resolved_title=resolved_title,
                    )
                )

            tags = sorted(item.tags, key=lambda t: t.id)
            actions = sorted(item.actions, key=lambda a: a.id)

            bundles.append(
                _IntelBundle(
                    intel=item,
                    entities=mentioned,
                    intel_tags=tags,
                    actions=actions,
                )
            )
        return iter(bundles)

    def query_ids(self, db: Session) -> Iterable[int]:
        return db.execute(select(IntelItem.id)).scalars()

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, row: _IntelBundle, ctx: RenderContext) -> NoteDoc:
        bundle = row
        intel = bundle.intel

        title = (intel.title or "").strip() or f"intel-{intel.id}"
        category = (intel.category or "uncategorized").strip() or "uncategorized"
        publisher = (intel.source or "").strip()
        url = (intel.url or "").strip()
        intel_status = _DEFAULT_INTEL_STATUS

        path = _shard_path(intel.id, intel.published_at, intel.created_at)

        tags = [
            f"bifrost/{_ENTITY_TYPE}",
            f"bifrost/status/{intel_status}",
            f"bifrost/intel/category/{category}",
        ]
        for tag_row in bundle.intel_tags:
            tag_value = (tag_row.tag or "").strip()
            if tag_value:
                tags.append(f"bifrost/intel/tag/{tag_value}")

        frontmatter: dict[str, Any] = {
            "bifrost_id": intel.id,
            "bifrost_type": _ENTITY_TYPE,
            "schema_version": ctx.schema_version,
            "title": title,
            "aliases": [title],
            "status": intel_status,
            "created_at": intel.created_at,
            "updated_at": intel.updated_at,
            "source": "bifrost",
            "tags": tags,
            "category": category,
            "source_name": publisher or None,
            "source_url_external": url or None,
            "published_at": intel.published_at,
            "relevance_score": intel.strategic_relevance_score,
            "intel_status": intel_status,
            "entities_count": len(bundle.entities),
            "actions_count": len(bundle.actions),
        }

        body = _build_body(
            intel_id=intel.id,
            title=title,
            publisher=publisher,
            published_at=intel.published_at,
            url=url,
            summary=intel.summary,
            entities=bundle.entities,
            intel_tags=bundle.intel_tags,
            actions=bundle.actions,
        )

        return NoteDoc(
            path=path,
            frontmatter=frontmatter,
            body=body,
            content_hash="",
        )

    def parents(self, row: _IntelBundle) -> list[ParentRef]:
        return []

    # ------------------------------------------------------------------
    # batch resolution of mentioned-entity titles
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_mentioned_titles(
        db: Session, items: list[IntelItem]
    ) -> dict[tuple[str, int], str]:
        """For every IntelEntity row whose entity_type is in the spec
        map AND has a non-null entity_id, look up the parent's display
        name. One IN-list query per supported type."""
        ids_by_type: dict[str, set[int]] = defaultdict(set)
        for item in items:
            for ie in item.entities:
                if ie.entity_id is None:
                    continue
                if ie.entity_type in _INTEL_ENTITY_SPECS:
                    ids_by_type[ie.entity_type].add(ie.entity_id)

        out: dict[tuple[str, int], str] = {}
        for entity_type, ids in ids_by_type.items():
            spec = _INTEL_ENTITY_SPECS.get(entity_type)
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
    intel_id: int,
    title: str,
    publisher: str,
    published_at: Optional[datetime],
    url: str,
    summary: Optional[str],
    entities: list[_MentionedEntity],
    intel_tags: list[IntelTag],
    actions: list[IntelAction],
) -> str:
    publisher_text = _escape_inline(publisher) if publisher else "—"
    published_text = _isoformat(published_at) if published_at else "—"
    link_text = url if url else "—"

    summary_block = (
        _normalize_text(summary) if summary and summary.strip() else "_(none)_"
    )

    parts = [
        f"# {_escape_inline(title)}",
        "",
        "## Source",
        "",
        f"- Publisher: {publisher_text}",
        f"- Published: {published_text}",
        f"- Link: {link_text}",
        "",
        "## Summary",
        "",
        summary_block,
        "",
        "## Mentioned Entities",
        "",
        _render_entities(entities),
        "",
        "## Tags",
        "",
        _render_tags(intel_tags),
        "",
        "## Recommended Actions",
        "",
        _render_actions(actions),
        "",
        "## Original Excerpt",
        "",
        # ``IntelItem`` has no excerpt column today. Render a placeholder
        # so the section exists and Dataview templates stay stable; when
        # an excerpt column is added, this becomes a one-line swap.
        "_(none)_",
        "",
        "## Provenance",
        "",
        f"- bifrost_id: {intel_id}",
        "- source: bifrost",
        "",
    ]
    return "\n".join(parts)


def _render_entities(entities: list[_MentionedEntity]) -> str:
    if not entities:
        return "_(none)_"
    lines: list[str] = []
    for me in entities:
        ie = me.intel_entity
        name = (ie.entity_name or "").strip() or f"{ie.entity_type}-{ie.id}"
        role = (ie.role or "").strip()
        role_suffix = f", role: {_escape_inline(role)}" if role else ""

        if (
            me.spec is not None
            and ie.entity_id is not None
        ):
            display = me.resolved_title or name
            lines.append(
                f"- [[{me.spec.prefix}-{ie.entity_id}|{_wiki_display(display)}]] "
                f"({ie.entity_type}{role_suffix})"
            )
        else:
            # Plain text fallback — either the type isn't mapped to a
            # registered transformer, or there's no internal pointer.
            lines.append(
                f"- {_escape_inline(name)} ({ie.entity_type}{role_suffix})"
            )
    return "\n".join(lines)


def _render_tags(intel_tags: list[IntelTag]) -> str:
    if not intel_tags:
        return "_(none)_"
    lines: list[str] = []
    for tag_row in intel_tags:
        tag_value = (tag_row.tag or "").strip()
        if not tag_value:
            continue
        lines.append(f"- {_escape_inline(tag_value)}")
    return "\n".join(lines) if lines else "_(none)_"


def _render_actions(actions: list[IntelAction]) -> str:
    if not actions:
        return "_(none)_"
    lines: list[str] = []
    for action in actions:
        action_type = (action.action_type or "").strip() or "action"
        status = (action.status or "").strip() or "—"
        recommendation = (action.recommended_action or "").strip()
        prefix = f"- {_escape_inline(action_type)} ({_escape_inline(status)})"
        if recommendation:
            lines.append(f"{prefix}: {_escape_inline(recommendation)}")
        else:
            lines.append(prefix)
    return "\n".join(lines)


# ----------------------------------------------------------------------
# path sharding
# ----------------------------------------------------------------------


def _shard_path(
    intel_id: int,
    published_at: Optional[datetime],
    created_at: Optional[datetime],
) -> str:
    when = published_at or created_at
    if when is None:
        year, month = "0000", "00"
    else:
        year = f"{when.year:04d}"
        month = f"{when.month:02d}"
    return f"{_FOLDER}/{year}/{month}/{_PREFIX}-{intel_id}.md"


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
