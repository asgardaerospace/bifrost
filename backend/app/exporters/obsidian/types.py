"""Data containers used across the Obsidian exporter.

Only structural types live here. Behavior (rendering, hashing, file
writes, manifest IO) belongs in dedicated modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(slots=True)
class NoteDoc:
    """A single rendered note ready to be written to the vault."""

    path: str
    frontmatter: dict[str, Any]
    body: str
    content_hash: str


@dataclass(slots=True)
class ManifestEntry:
    """One row in ``_meta/manifest.json``, keyed by ``{prefix}-{id}``."""

    path: str
    content_hash: str
    schema_version: int
    exported_at: datetime
    deleted_at: Optional[datetime] = None
    archived: bool = False


@dataclass(slots=True)
class ExportResult:
    """Aggregate counters for one exporter run."""

    written: int = 0
    unchanged: int = 0
    archived: int = 0
    restored: int = 0
    errors: int = 0


@dataclass(slots=True, frozen=True)
class ParentRef:
    """A pointer from a child row to a parent that must be re-rendered.

    Emitted by ``EntityTransformer.parents()`` and consumed by the
    coordinator's reverse-touch pass.
    """

    entity_type: str
    entity_id: int


@dataclass(slots=True)
class RenderContext:
    """Per-run context handed to every transformer's ``render()`` call.

    Kept intentionally small — anything that varies per row belongs on
    the row itself, not here.
    """

    exported_at: datetime
    schema_version: int = 1
    extras: dict[str, Any] = field(default_factory=dict)
