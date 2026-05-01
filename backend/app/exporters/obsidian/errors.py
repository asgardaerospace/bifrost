"""Exception hierarchy for the Obsidian exporter.

All exporter failures derive from :class:`ExportError` so callers
(CLI, API route, scheduler) can catch one type at the boundary.
"""

from __future__ import annotations


class ExportError(Exception):
    """Base class for all exporter failures."""


class ManifestLockedError(ExportError):
    """Raised when another exporter run holds ``_meta/.lock``."""


class ValidationError(ExportError):
    """Raised when exporter inputs or outputs fail invariants.

    Distinct from ``pydantic.ValidationError``; this one signals an
    invariant violation inside the exporter (bad path, unknown entity
    type, malformed manifest, etc.) rather than a schema mismatch on
    user input.
    """
