"""Transformer for ``suppliers`` rows.

Produces one note per supplier at
``Bifrost/Suppliers/supplier-{id}.md``.

Performance contract — for a batch of N suppliers:
    * 1 main query for suppliers (with selectinload on capabilities and
      certifications)
    * 1 query for program_suppliers joined to programs (Programs section)
    * 1 query each for meetings/communications/notes filtered with
      ``entity_type='supplier' AND entity_id IN (...)``

Parent refs: empty. Suppliers are top-of-tree from the exporter's
perspective. Children (programs that reference them) will trigger
refresh through the coordinator's existing reverse-touch path.
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
from app.models.meeting import Meeting
from app.models.note import Note
from app.models.program import Program
from app.models.supplier import (
    ProgramSupplier,
    Supplier,
    SupplierCapability,
    SupplierCertification,
)


_ENTITY_TYPE = "supplier"
_PREFIX = "supplier"
_FOLDER = "Bifrost/Suppliers"
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
class _SupplierBundle:
    supplier: Supplier
    capabilities: list[SupplierCapability]
    certifications: list[SupplierCertification]
    programs: list[tuple[Program, str, str]]  # (program, role, status)
    recent: list[_RecentItem]

    @property
    def id(self) -> int:
        return self.supplier.id

    @property
    def deleted_at(self) -> Optional[datetime]:
        return self.supplier.deleted_at


# ----------------------------------------------------------------------
# transformer
# ----------------------------------------------------------------------


class SupplierTransformer:
    entity_type: str = _ENTITY_TYPE
    prefix: str = _PREFIX

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def query_changed(
        self, db: Session, since: datetime | None
    ) -> Iterable[_SupplierBundle]:
        stmt = (
            select(Supplier)
            .options(
                selectinload(Supplier.capabilities),
                selectinload(Supplier.certifications),
            )
            .order_by(Supplier.id)
        )
        if since is not None:
            stmt = stmt.where(
                or_(
                    Supplier.updated_at > since,
                    Supplier.deleted_at > since,
                )
            )

        suppliers: list[Supplier] = list(db.execute(stmt).scalars().all())
        if not suppliers:
            return iter([])

        supplier_ids = [s.id for s in suppliers]

        programs_by_supplier = self._load_programs(db, supplier_ids)
        recent_by_supplier = self._load_recent(db, supplier_ids)

        bundles: list[_SupplierBundle] = []
        for s in suppliers:
            capabilities = sorted(s.capabilities, key=lambda c: c.id)
            certifications = sorted(s.certifications, key=lambda c: c.id)
            bundles.append(
                _SupplierBundle(
                    supplier=s,
                    capabilities=capabilities,
                    certifications=certifications,
                    programs=programs_by_supplier.get(s.id, []),
                    recent=recent_by_supplier.get(s.id, []),
                )
            )
        return iter(bundles)

    def query_ids(self, db: Session) -> Iterable[int]:
        return db.execute(select(Supplier.id)).scalars()

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, row: _SupplierBundle, ctx: RenderContext) -> NoteDoc:
        bundle = row
        supplier = bundle.supplier

        title = (supplier.name or "").strip() or f"Untitled supplier {supplier.id}"
        supplier_type = (supplier.type or "").strip()
        region = (supplier.region or "").strip()
        country = (supplier.country or "").strip()
        website = (supplier.website or "").strip()
        onboarding = (supplier.onboarding_status or "").strip()

        # Suppliers have no own ``status`` column; lifecycle is via
        # ``deleted_at``. Use a fixed value for tag symmetry; track
        # onboarding state separately as ``onboarding_status``.
        status = "active"

        path = f"{_FOLDER}/{_PREFIX}-{supplier.id}.md"

        tags = [f"bifrost/{_ENTITY_TYPE}", f"bifrost/status/{status}"]
        if onboarding:
            tags.append(f"bifrost/onboarding/{onboarding}")

        frontmatter: dict[str, Any] = {
            "bifrost_id": supplier.id,
            "bifrost_type": _ENTITY_TYPE,
            "schema_version": ctx.schema_version,
            "title": title,
            "aliases": [title],
            "status": status,
            "created_at": supplier.created_at,
            "updated_at": supplier.updated_at,
            "source": "bifrost",
            "tags": tags,
            "supplier_type": supplier_type or None,
            "region": region or None,
            "country": country or None,
            "website": website or None,
            "onboarding_status": onboarding or None,
            "preferred_partner_score": supplier.preferred_partner_score,
            "capabilities_count": len(bundle.capabilities),
            "certifications_count": len(bundle.certifications),
            "programs_count": len(bundle.programs),
        }

        body = _build_body(
            supplier_id=supplier.id,
            title=title,
            description=supplier.notes,
            capabilities=bundle.capabilities,
            certifications=bundle.certifications,
            programs=bundle.programs,
            recent=bundle.recent,
        )

        return NoteDoc(
            path=path,
            frontmatter=frontmatter,
            body=body,
            content_hash="",
        )

    def parents(self, row: _SupplierBundle) -> list[ParentRef]:
        return []

    # ------------------------------------------------------------------
    # batch loaders
    # ------------------------------------------------------------------

    @staticmethod
    def _load_programs(
        db: Session, supplier_ids: list[int]
    ) -> dict[int, list[tuple[Program, str, str]]]:
        out: dict[int, list[tuple[Program, str, str]]] = defaultdict(list)
        if not supplier_ids:
            return out
        stmt = (
            select(
                ProgramSupplier.supplier_id,
                Program,
                ProgramSupplier.role,
                ProgramSupplier.status,
            )
            .join(Program, Program.id == ProgramSupplier.program_id)
            .where(ProgramSupplier.supplier_id.in_(supplier_ids))
            .where(Program.deleted_at.is_(None))
            .order_by(Program.id)
        )
        for supplier_id, program, role, status in db.execute(stmt).all():
            out[supplier_id].append((program, role or "", status or ""))
        return out

    @classmethod
    def _load_recent(
        cls, db: Session, supplier_ids: list[int]
    ) -> dict[int, list[_RecentItem]]:
        out: dict[int, list[_RecentItem]] = defaultdict(list)
        if not supplier_ids:
            return out

        # Meetings.
        m_stmt = select(Meeting).where(
            Meeting.entity_type == _ENTITY_TYPE,
            Meeting.entity_id.in_(supplier_ids),
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

        # Communications — column-select to bypass DB drift on the
        # optional ``source_system``/``source_external_id`` columns.
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
            Communication.entity_id.in_(supplier_ids),
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

        # Notes — display constructed at render time so the supplier
        # name in the bundle stays the source of truth.
        n_stmt = select(Note).where(
            Note.entity_type == _ENTITY_TYPE,
            Note.entity_id.in_(supplier_ids),
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
        for sid, items in out.items():
            items.sort(key=lambda x: (x.kind, x.id))
            items.sort(key=lambda x: x.when or _MIN_DT, reverse=True)
            out[sid] = items[:_ACTIVITY_LIMIT]
        return out


# ----------------------------------------------------------------------
# body assembly
# ----------------------------------------------------------------------


def _build_body(
    *,
    supplier_id: int,
    title: str,
    description: Optional[str],
    capabilities: list[SupplierCapability],
    certifications: list[SupplierCertification],
    programs: list[tuple[Program, str, str]],
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
        "## Capabilities",
        "",
        _render_capabilities(capabilities),
        "",
        "## Certifications",
        "",
        _render_certifications(certifications),
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
        f"- bifrost_id: {supplier_id}",
        "- source: bifrost",
        "",
    ]
    return "\n".join(parts)


def _render_capabilities(capabilities: list[SupplierCapability]) -> str:
    if not capabilities:
        return "_(none)_"
    lines = [
        "| Capability | Description |",
        "|---|---|",
    ]
    for cap in capabilities:
        capability = (cap.capability_type or "").strip() or "—"
        description = (cap.description or "").strip() or "—"
        lines.append(
            "| " + " | ".join(_cell(v) for v in (capability, description)) + " |"
        )
    return "\n".join(lines)


def _render_certifications(certifications: list[SupplierCertification]) -> str:
    if not certifications:
        return "_(none)_"
    lines = [
        "| Certification | Status | Expiration |",
        "|---|---|---|",
    ]
    for cert in certifications:
        certification = (cert.certification or "").strip() or "—"
        status = (cert.status or "").strip() or "—"
        expiration = (
            cert.expiration_date.isoformat() if cert.expiration_date else "—"
        )
        lines.append(
            "| "
            + " | ".join(_cell(v) for v in (certification, status, expiration))
            + " |"
        )
    return "\n".join(lines)


def _render_programs(programs: list[tuple[Program, str, str]]) -> str:
    if not programs:
        return "_(none)_"
    lines: list[str] = []
    for program, role, status in programs:
        name = (program.name or "").strip() or f"program-{program.id}"
        role_text = role.strip() or "—"
        status_text = status.strip() or "—"
        lines.append(
            f"- [[program-{program.id}|{_wiki_display(name)}]] — "
            f"role: {_escape_inline(role_text)}, "
            f"status: {_escape_inline(status_text)}"
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


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


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
