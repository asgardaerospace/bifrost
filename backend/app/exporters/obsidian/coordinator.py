"""Minimal orchestrator for an Obsidian export run.

Two-pass execution:

    1. Main pass — iterate registered transformers in order. For each
       row, render and write/skip per content hash. When a row is
       actually written/archived/restored, collect its parent refs
       into ``_dirty_parents``.

    2. Reverse-touch pass — for each parent entity_type with dirty
       refs, find the matching transformer, query those rows, and
       re-render. Skips ids already touched in the main pass (their
       file is already current) and never collects further parent
       refs (one-level-only by design — no recursive cascades).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from app.exporters.obsidian.errors import ExportError, ValidationError
from app.exporters.obsidian.manifest import ManifestManager
from app.exporters.obsidian.transformers.base import EntityTransformer
from app.exporters.obsidian.types import (
    ExportResult,
    ManifestEntry,
    NoteDoc,
    ParentRef,
    RenderContext,
)
from app.exporters.obsidian.writer import FileWriter

logger = logging.getLogger(__name__)


_BACKWINDOW = timedelta(minutes=5)
_DEFAULT_SCHEMA_VERSION = 1


class SyncCoordinator:
    """Single-run orchestrator. Construct, ``run()`` once, discard."""

    def __init__(
        self,
        *,
        vault_root: str | Path,
        session,
        transformers: list[EntityTransformer],
        schema_version: int = _DEFAULT_SCHEMA_VERSION,
    ) -> None:
        if not transformers:
            raise ValidationError("SyncCoordinator requires at least one transformer")
        self._vault_root = Path(vault_root)
        self._session = session
        self._transformers = transformers
        self._schema_version = schema_version
        self._manifest = ManifestManager(vault_root)
        self._writer = FileWriter(vault_root)

        # Per-run state. Reset at the top of run() so a coordinator can
        # in principle be reused, though that's not the intended use.
        self._dirty_parents: dict[str, set[int]] = defaultdict(set)
        self._processed_ids: dict[str, set[int]] = defaultdict(set)

    # ------------------------------------------------------------------
    # entrypoint
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        mode: str,
        since: datetime | None = None,
    ) -> dict[str, ExportResult]:
        if mode not in ("full", "incremental"):
            raise ValidationError(f"unknown mode: {mode!r}")

        self._dirty_parents = defaultdict(set)
        self._processed_ids = defaultdict(set)

        run_started_at = _utcnow()
        ctx = RenderContext(
            exported_at=run_started_at,
            schema_version=self._schema_version,
        )
        results: dict[str, ExportResult] = {}

        self._manifest.acquire_lock()
        try:
            self._manifest.load_manifest()
            effective_since = self._resolve_since(mode, since)

            # --- pass 1: main transformer loop ---
            for transformer in self._transformers:
                logger.info(
                    "starting transformer entity_type=%s since=%s",
                    transformer.entity_type,
                    effective_since.isoformat() if effective_since else None,
                )
                result = self._run_transformer(transformer, effective_since, ctx)
                results[transformer.entity_type] = result
                self._advance_last_export_at(transformer.entity_type, run_started_at)
                logger.info(
                    "finished transformer entity_type=%s result=%s",
                    transformer.entity_type,
                    asdict(result),
                )

            # --- pass 2: reverse-touch parent refresh ---
            self._refresh_dirty_parents(ctx, results, run_started_at)

            self._manifest.save_manifest()
        finally:
            self._manifest.release_lock()

        return results

    # ------------------------------------------------------------------
    # main pass
    # ------------------------------------------------------------------

    def _run_transformer(
        self,
        transformer: EntityTransformer,
        since: datetime | None,
        ctx: RenderContext,
    ) -> ExportResult:
        result = ExportResult()
        rows: Iterable[Any] = transformer.query_changed(self._session, since)
        for row in rows:
            try:
                self._process_row(transformer, row, ctx, result)
            except ExportError as exc:
                row_id = getattr(row, "id", None)
                logger.error(
                    "row export failed entity_type=%s id=%s: %s",
                    transformer.entity_type,
                    row_id,
                    exc,
                )
                result.errors += 1
            except Exception as exc:  # noqa: BLE001
                row_id = getattr(row, "id", None)
                logger.exception(
                    "row export crashed entity_type=%s id=%s",
                    transformer.entity_type,
                    row_id,
                )
                result.errors += 1
        return result

    def _process_row(
        self,
        transformer: EntityTransformer,
        row: Any,
        ctx: RenderContext,
        result: ExportResult,
        *,
        collect_parents: bool = True,
    ) -> None:
        row_id = getattr(row, "id", None)
        if not isinstance(row_id, int):
            raise ExportError(
                f"row from {transformer.entity_type} has non-int id: {row_id!r}"
            )

        # Mark this id as processed regardless of write/skip outcome.
        # Reverse-touch uses this to avoid double-processing parents
        # whose file is already current after the main pass.
        self._processed_ids[transformer.entity_type].add(row_id)

        key = f"{transformer.prefix}-{row_id}"
        existing = self._manifest.get_entry(key)

        deleted_at = getattr(row, "deleted_at", None)
        is_archived = deleted_at is not None

        note = transformer.render(row, ctx)

        live_path = note.path
        archive_path = _to_archive_path(live_path)
        target_path = archive_path if is_archived else live_path

        fm_for_hash: dict[str, Any] = dict(note.frontmatter)
        fm_for_hash["archived"] = is_archived
        fm_for_hash["deleted_at"] = deleted_at

        content_hash = _compute_content_hash(fm_for_hash, note.body)
        note.content_hash = content_hash

        if (
            existing is not None
            and existing.content_hash == content_hash
            and existing.path == target_path
            and existing.archived == is_archived
        ):
            result.unchanged += 1
            # Per spec: do NOT collect parent refs for unchanged rows.
            return

        fm_full: dict[str, Any] = dict(fm_for_hash)
        fm_full["exported_at"] = ctx.exported_at
        fm_full["content_hash"] = content_hash
        final_text = _assemble_markdown(fm_full, note.body)

        if existing is not None and existing.archived and not is_archived:
            self._writer.restore_file(existing.path, live_path)

        self._writer.write_atomic(live_path, final_text)
        if is_archived:
            self._writer.archive_file(live_path, archive_path)

        if existing is None:
            if is_archived:
                result.archived += 1
            else:
                result.written += 1
        elif existing.archived and not is_archived:
            result.restored += 1
        elif not existing.archived and is_archived:
            result.archived += 1
        else:
            result.written += 1

        self._manifest.upsert_entry(
            key,
            ManifestEntry(
                path=target_path,
                content_hash=content_hash,
                schema_version=ctx.schema_version,
                exported_at=ctx.exported_at,
                deleted_at=deleted_at,
                archived=is_archived,
            ),
        )

        # Reverse-touch: only collect parents on rows that actually
        # changed (written/archived/restored), and only during the
        # main pass — the refresh pass disables this to keep the
        # cascade strictly one level deep.
        if collect_parents:
            self._collect_parent_refs(transformer, row)

    def _collect_parent_refs(
        self, transformer: EntityTransformer, row: Any
    ) -> None:
        try:
            refs = transformer.parents(row)
        except Exception:  # noqa: BLE001
            row_id = getattr(row, "id", None)
            logger.exception(
                "transformer.parents() raised entity_type=%s id=%s",
                transformer.entity_type,
                row_id,
            )
            return

        for ref in refs or ():
            if not isinstance(ref, ParentRef):
                logger.warning(
                    "transformer.parents() returned non-ParentRef "
                    "entity_type=%s value=%r",
                    transformer.entity_type,
                    ref,
                )
                continue
            if not isinstance(ref.entity_id, int):
                logger.warning(
                    "ParentRef has non-int entity_id entity_type=%s "
                    "value=%r",
                    transformer.entity_type,
                    ref,
                )
                continue
            self._dirty_parents[ref.entity_type].add(ref.entity_id)

    # ------------------------------------------------------------------
    # reverse-touch pass
    # ------------------------------------------------------------------

    def _refresh_dirty_parents(
        self,
        ctx: RenderContext,
        results: dict[str, ExportResult],
        run_started_at: datetime,
    ) -> None:
        if not self._dirty_parents:
            return

        # Snapshot the type keys — defensive, since processing rows
        # via _process_row(collect_parents=False) won't add new ones,
        # but iterating a defaultdict during mutation is brittle.
        for parent_type in list(self._dirty_parents.keys()):
            candidate_ids = set(self._dirty_parents[parent_type])
            already_processed = self._processed_ids.get(parent_type, set())
            ids_to_refresh = candidate_ids - already_processed

            transformer = self._find_transformer(parent_type)
            if transformer is None:
                logger.warning(
                    "parent refresh skipped entity_type=%s "
                    "reason=no_registered_transformer candidates=%d",
                    parent_type,
                    len(candidate_ids),
                )
                continue

            if not ids_to_refresh:
                logger.debug(
                    "parent refresh no-op entity_type=%s "
                    "(all %d candidates already processed in main pass)",
                    parent_type,
                    len(candidate_ids),
                )
                continue

            logger.info(
                "parent refresh entity_type=%s candidates=%d "
                "already_processed=%d to_refresh=%d",
                parent_type,
                len(candidate_ids),
                len(candidate_ids & already_processed),
                len(ids_to_refresh),
            )

            # Reuse the main-pass result counter if the transformer
            # already ran; otherwise create a fresh one. Either way,
            # parent-refresh writes accumulate into the same struct
            # the caller sees in the final ExportResult dict.
            result = results.get(parent_type)
            if result is None:
                result = ExportResult()
                results[parent_type] = result

            rows = self._load_rows_by_ids(transformer, ids_to_refresh)
            for row in rows:
                try:
                    self._process_row(
                        transformer, row, ctx, result, collect_parents=False
                    )
                except ExportError as exc:
                    logger.error(
                        "parent refresh row failed entity_type=%s id=%s: %s",
                        parent_type,
                        getattr(row, "id", None),
                        exc,
                    )
                    result.errors += 1
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "parent refresh row crashed entity_type=%s id=%s",
                        parent_type,
                        getattr(row, "id", None),
                    )
                    result.errors += 1

            # Advance the parent type's last_export_at — incremental
            # runs that triggered this refresh would otherwise re-do
            # the same parent on the next run.
            self._advance_last_export_at(parent_type, run_started_at)

    def _find_transformer(self, entity_type: str) -> EntityTransformer | None:
        for t in self._transformers:
            if t.entity_type == entity_type:
                return t
        return None

    def _load_rows_by_ids(
        self, transformer: EntityTransformer, ids: set[int]
    ) -> list[Any]:
        """Load specific parent rows for the refresh pass.

        Extension point: a transformer can opt into a fast path by
        defining ``query_by_ids(db, ids) -> Iterable[row]``. Without
        it, the coordinator falls back to scanning ``query_changed
        (db, None)`` and filtering in Python — correct, but O(N) in
        the size of the parent table. Acceptable at dev scale; flag
        for tuning when any parent type crosses ~10k rows.
        """
        qbi = getattr(transformer, "query_by_ids", None)
        if callable(qbi):
            return list(qbi(self._session, list(ids)))
        id_set = set(ids)
        out: list[Any] = []
        for row in transformer.query_changed(self._session, None):
            if getattr(row, "id", None) in id_set:
                out.append(row)
        return out

    # ------------------------------------------------------------------
    # since resolution + meta
    # ------------------------------------------------------------------

    def _resolve_since(
        self,
        mode: str,
        explicit_since: datetime | None,
    ) -> datetime | None:
        if mode == "full":
            return None
        if explicit_since is not None:
            return explicit_since

        data = self._manifest.load_manifest()
        last = data.get("meta", {}).get("last_export_at", {}) or {}
        timestamps: list[datetime] = []
        for transformer in self._transformers:
            raw = last.get(transformer.entity_type)
            if not isinstance(raw, str):
                continue
            try:
                timestamps.append(_parse_iso(raw))
            except ValueError:
                continue

        if not timestamps:
            return None
        return min(timestamps) - _BACKWINDOW

    def _advance_last_export_at(
        self, entity_type: str, started_at: datetime
    ) -> None:
        data = self._manifest.load_manifest()
        meta = data.setdefault("meta", {})
        last = meta.setdefault("last_export_at", {})
        last[entity_type] = started_at.isoformat()


# ----------------------------------------------------------------------
# helpers — markdown assembly + hashing
# ----------------------------------------------------------------------


def _assemble_markdown(frontmatter: dict[str, Any], body: str) -> str:
    yaml = _to_yaml(frontmatter)
    body = body if body.endswith("\n") else body + "\n"
    return f"---\n{yaml}\n---\n\n{body}"


def _compute_content_hash(frontmatter: dict[str, Any], body: str) -> str:
    payload = json.dumps(
        frontmatter,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    )
    payload = payload + "\n---\n" + body
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return _isoformat(value)
    raise TypeError(f"unhashable type in frontmatter: {type(value).__name__}")


# ----------------------------------------------------------------------
# helpers — minimal deterministic YAML
# ----------------------------------------------------------------------


def _to_yaml(d: dict[str, Any]) -> str:
    lines: list[str] = []
    for key in d:
        lines.append(_yaml_pair(key, d[key]))
    return "\n".join(lines)


def _yaml_pair(key: str, value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return f"{key}: []"
        out = [f"{key}:"]
        for item in value:
            out.append(f"  - {_yaml_scalar(item)}")
        return "\n".join(out)
    return f"{key}: {_yaml_scalar(value)}"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    if isinstance(value, datetime):
        return _isoformat(value)
    if isinstance(value, str):
        return _yaml_string(value)
    return _yaml_string(str(value))


def _yaml_string(value: str) -> str:
    cleaned = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
    )
    return f'"{cleaned}"'


# ----------------------------------------------------------------------
# helpers — paths + datetime
# ----------------------------------------------------------------------


def _to_archive_path(live_path: str) -> str:
    parts = live_path.replace("\\", "/").split("/")
    if not parts or parts[0] != "Bifrost":
        raise ExportError(f"unexpected note path shape: {live_path!r}")
    if len(parts) >= 2 and parts[1] == "_archive":
        return live_path
    return "/".join(("Bifrost", "_archive", *parts[1:]))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    s = dt.isoformat()
    return s[:-6] + "Z" if s.endswith("+00:00") else s


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
