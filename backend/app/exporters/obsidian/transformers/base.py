"""Protocol every entity transformer must satisfy.

Transformers are pure: they query the DB and return :class:`NoteDoc`
values. They never write files and never mutate the manifest — the
coordinator owns those side effects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.exporters.obsidian.types import NoteDoc, ParentRef, RenderContext


@runtime_checkable
class EntityTransformer(Protocol):
    """One implementation per Bifrost entity type."""

    entity_type: str
    prefix: str

    def query_changed(
        self, db: Session, since: datetime | None
    ) -> Iterable[Any]:
        ...

    def query_ids(self, db: Session) -> Iterable[int]:
        ...

    def render(self, row: Any, ctx: RenderContext) -> NoteDoc:
        ...

    def parents(self, row: Any) -> list[ParentRef]:
        ...
