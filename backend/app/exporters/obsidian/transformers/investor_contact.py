"""Transformer for ``investor_contacts`` rows.

Produces one note per contact at
``Bifrost/Investors/Contacts/contact-{id}.md``. The note carries a
parent-link wikilink back to its firm in both frontmatter (machine-
readable, Dataview-friendly) and body (so Obsidian's graph view shows
the relationship).

``parents()`` returns a single :class:`ParentRef` pointing at the
firm. The minimal v1 coordinator does not yet act on these — once the
reverse-touch pass lands, contact edits will trigger their firm note
to be re-rendered automatically.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.exporters.obsidian.types import NoteDoc, ParentRef, RenderContext
from app.models.investor import InvestorContact


_ENTITY_TYPE = "investor_contact"
_PREFIX = "contact"
_FOLDER = "Bifrost/Investors/Contacts"


class InvestorContactTransformer:
    entity_type: str = _ENTITY_TYPE
    prefix: str = _PREFIX

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def query_changed(
        self, db: Session, since: datetime | None
    ) -> Iterable[InvestorContact]:
        stmt = (
            select(InvestorContact)
            .options(selectinload(InvestorContact.firm))
            .order_by(InvestorContact.id)
        )
        if since is not None:
            stmt = stmt.where(
                or_(
                    InvestorContact.updated_at > since,
                    InvestorContact.deleted_at > since,
                )
            )
        stmt = stmt.execution_options(yield_per=500)
        return db.execute(stmt).scalars()

    def query_ids(self, db: Session) -> Iterable[int]:
        return db.execute(select(InvestorContact.id)).scalars()

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    def render(self, row: InvestorContact, ctx: RenderContext) -> NoteDoc:
        contact = row
        firm = getattr(contact, "firm", None)

        name = (contact.name or "").strip() or f"Untitled investor_contact {contact.id}"
        role = (contact.title or "").strip()
        email = (contact.email or "").strip()
        phone = (contact.phone or "").strip()
        linkedin = (contact.linkedin_url or "").strip()

        firm_name_raw = (firm.name if firm and firm.name else "").strip()
        firm_display = firm_name_raw or f"firm-{contact.firm_id}"
        firm_link = f"[[firm-{contact.firm_id}|{_wiki_display(firm_display)}]]"

        # Contact has no own ``status`` column; soft-delete is handled
        # by the coordinator via ``deleted_at``. Use a fixed value so
        # the tag/dataview surface matches other entity types.
        status = "active"

        path = f"{_FOLDER}/{_PREFIX}-{contact.id}.md"

        aliases: list[str] = [name]
        if email and email != name:
            aliases.append(email)

        frontmatter: dict[str, Any] = {
            "bifrost_id": contact.id,
            "bifrost_type": _ENTITY_TYPE,
            "schema_version": ctx.schema_version,
            "title": name,
            "aliases": aliases,
            "status": status,
            "created_at": contact.created_at,
            "updated_at": contact.updated_at,
            "source": "bifrost",
            "tags": [
                f"bifrost/{_ENTITY_TYPE}",
                f"bifrost/status/{status}",
            ],
            "firm_id": contact.firm_id,
            "firm": firm_link,
            "name": name,
            "role": role or None,
            "email": email or None,
            "phone": phone or None,
            "linkedin_url": linkedin or None,
        }

        body = _build_body(
            contact_id=contact.id,
            name=name,
            role=role,
            firm_link=firm_link,
            email=email,
            phone=phone,
            linkedin=linkedin,
            notes=contact.notes,
        )

        return NoteDoc(
            path=path,
            frontmatter=frontmatter,
            body=body,
            content_hash="",
        )

    def parents(self, row: InvestorContact) -> list[ParentRef]:
        return [ParentRef(entity_type="investor_firm", entity_id=row.firm_id)]


# ----------------------------------------------------------------------
# body assembly
# ----------------------------------------------------------------------


def _build_body(
    *,
    contact_id: int,
    name: str,
    role: str,
    firm_link: str,
    email: str,
    phone: str,
    linkedin: str,
    notes: Optional[str],
) -> str:
    role_line = f"- Title: {_escape_inline(role) if role else '—'}"
    email_line = f"- Email: {_escape_inline(email) if email else '—'}"
    phone_line = f"- Phone: {_escape_inline(phone) if phone else '—'}"
    linkedin_line = f"- LinkedIn: {_escape_inline(linkedin) if linkedin else '—'}"
    notes_block = _normalize_text(notes) if notes else "_(none)_"

    parts = [
        f"# {_escape_inline(name)}",
        "",
        "## Role",
        "",
        role_line,
        f"- Firm: {firm_link}",
        "",
        "## Contact",
        "",
        email_line,
        phone_line,
        linkedin_line,
        "",
        "## Notes",
        "",
        notes_block,
        "",
        "## Provenance",
        "",
        f"- bifrost_id: {contact_id}",
        "- source: bifrost",
        "",
    ]
    return "\n".join(parts)


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
