"""Read-only reconciler for the Obsidian exporter.

Walks the vault tree under ``{vault_root}/Bifrost/`` and cross-
references it against the manifest. Returns a structured
:class:`ReconcileReport` describing every kind of drift we know how
to detect:

    * ``orphan_files``       — exist on disk, no manifest entry
    * ``missing_files``      — manifest entry exists, file is missing
    * ``invalid_files``      — filename violates ``^[a-z]+-\\d+\\.md$``
    * ``archive_mismatches`` — manifest disagrees with the file's tree
                               (live vs ``_archive/``) or with its
                               canonical path

Mutates nothing. Operator-driven cleanup is intentionally a separate
step — a corrupted vault should never be auto-rewritten by something
running in audit mode.

Performance: a single ``Path.rglob('*.md')`` walk over the Bifrost
subtree, plus one manifest load. O(N + M) in file and entry count.
At 100k files / 100k entries the report builds in a few seconds and
peaks well under 100 MB of memory.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.exporters.obsidian.manifest import ManifestManager


# Layout under vault_root.
_BIFROST_DIR = "Bifrost"
_META_DIR = "_meta"
_ARCHIVE_DIR = "_archive"
_BRIEFS_DIR = "Briefs"

# Top-level subtrees the reconciler walks past entirely. ``_meta/`` is
# owned by ManifestManager. ``Briefs/`` holds user-facing artifacts
# (daily briefs) whose filenames don't and shouldn't match the canonical
# note regex — they're not exporter-tracked, so they should never
# appear in any drift category. ``_archive/`` is intentionally NOT in
# this set: archived notes still have manifest entries and must be
# reconciled.
_INVISIBLE_TOP_LEVEL: frozenset[str] = frozenset({_META_DIR, _BRIEFS_DIR})

# Canonical note-filename shape — must stay in sync with FileWriter.
_FILENAME_RE = re.compile(r"^[a-z]+-\d+\.md$")


# ----------------------------------------------------------------------
# report
# ----------------------------------------------------------------------


@dataclass(slots=True)
class ReconcileReport:
    """Structured audit of vault ↔ manifest drift.

    All path lists are vault-relative (``Bifrost/...``) and sorted for
    deterministic output. Empty lists mean "no issues of that kind".
    """

    orphan_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    invalid_files: list[str] = field(default_factory=list)
    archive_mismatches: list[str] = field(default_factory=list)

    files_scanned: int = 0
    manifest_entries: int = 0

    @property
    def total_issues(self) -> int:
        return (
            len(self.orphan_files)
            + len(self.missing_files)
            + len(self.invalid_files)
            + len(self.archive_mismatches)
        )

    @property
    def is_clean(self) -> bool:
        return self.total_issues == 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ----------------------------------------------------------------------
# entrypoint
# ----------------------------------------------------------------------


def reconcile_vault(vault_root: str | Path) -> ReconcileReport:
    """Audit the vault against the manifest. Read-only.

    Returns a populated :class:`ReconcileReport`. The manifest is
    loaded via :class:`ManifestManager` so the same backup-fallback
    rules apply — an unreadable manifest with no usable backup will
    raise :class:`ExportError` from the manager rather than producing
    a misleadingly-empty report.
    """
    vault = Path(vault_root)
    bifrost = vault / _BIFROST_DIR

    report = ReconcileReport()
    if not bifrost.exists() or not bifrost.is_dir():
        # No vault yet — nothing to compare.
        return report

    files_by_key: dict[str, _FileInfo] = _scan_vault(bifrost, report)

    # Read the manifest. No lock acquired: ManifestManager flushes
    # atomically, so any concurrent writer is observed before-or-after,
    # never partial.
    manifest = ManifestManager(vault)
    data = manifest.load_manifest()
    entries: dict[str, Any] = data.get("entries", {}) or {}
    report.manifest_entries = len(entries)

    _cross_check_files_vs_manifest(files_by_key, entries, report)
    _cross_check_manifest_vs_files(files_by_key, entries, report)

    # Deterministic output regardless of OS walk order.
    report.orphan_files.sort()
    report.missing_files.sort()
    report.invalid_files.sort()
    report.archive_mismatches.sort()

    return report


# ----------------------------------------------------------------------
# internals
# ----------------------------------------------------------------------


@dataclass(slots=True)
class _FileInfo:
    key: str
    path: str
    is_archived: bool


def _scan_vault(
    bifrost: Path, report: ReconcileReport
) -> dict[str, _FileInfo]:
    """Walk the Bifrost tree once. Populate the by-key dict and the
    report's ``invalid_files`` list. Skips ``_meta/`` (owned by the
    manifest manager) and silently ignores non-``.md`` files (anything
    else under Bifrost/ is treated as user content)."""
    files_by_key: dict[str, _FileInfo] = {}

    for path in bifrost.rglob("*.md"):
        try:
            rel = path.relative_to(bifrost)
        except ValueError:
            # Symlink chicanery — shouldn't happen, but keep walking.
            continue

        parts = rel.parts
        if not parts or parts[0] in _INVISIBLE_TOP_LEVEL:
            continue

        rel_str = "/".join((_BIFROST_DIR, *parts))
        report.files_scanned += 1

        if not _FILENAME_RE.match(path.name):
            report.invalid_files.append(rel_str)
            continue

        is_archived = parts[0] == _ARCHIVE_DIR
        key = path.stem  # ``firm-1234``

        existing = files_by_key.get(key)
        if existing is not None:
            # The same key appearing in two locations means the vault
            # has both a live and an archive copy (or a duplicate).
            # Surface as an archive mismatch so the operator can pick.
            report.archive_mismatches.append(rel_str)
            # Keep the first one we saw; let the duplicate be the
            # flagged mismatch.
            continue

        files_by_key[key] = _FileInfo(
            key=key, path=rel_str, is_archived=is_archived
        )

    return files_by_key


def _cross_check_files_vs_manifest(
    files_by_key: dict[str, _FileInfo],
    entries: dict[str, Any],
    report: ReconcileReport,
) -> None:
    for key, info in files_by_key.items():
        entry = entries.get(key)
        if entry is None:
            report.orphan_files.append(info.path)
            continue

        manifest_archived = bool(entry.get("archived", False))
        manifest_path = entry.get("path")

        if manifest_archived != info.is_archived:
            report.archive_mismatches.append(info.path)
            continue

        if isinstance(manifest_path, str) and manifest_path != info.path:
            # Same archive flag but the file lives at a different path
            # than the manifest claims — e.g. the transformer's folder
            # layout changed without a re-export.
            report.archive_mismatches.append(info.path)


def _cross_check_manifest_vs_files(
    files_by_key: dict[str, _FileInfo],
    entries: dict[str, Any],
    report: ReconcileReport,
) -> None:
    keys_on_disk = files_by_key.keys()
    for key, entry in entries.items():
        if key in keys_on_disk:
            continue
        # Manifest expects a file that isn't there.
        path = entry.get("path") if isinstance(entry, dict) else None
        report.missing_files.append(path if isinstance(path, str) else key)
