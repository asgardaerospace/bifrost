"""Manifest manager for the Obsidian exporter.

Owns the on-disk state file at ``{vault_root}/Bifrost/_meta/manifest.json``
and the run lock at ``{vault_root}/Bifrost/_meta/.lock``.

Design contract:
    * Load once into memory at the start of a run.
    * All mutations (``upsert_entry``/``mark_archived``/``remove_entry``)
      operate on the in-memory dict — no I/O.
    * Coordinator calls ``save_manifest()`` at entity-type boundaries and
      at run end. Writes are atomic (temp file → fsync → rename).
    * The previous on-disk manifest is copied to ``manifest.json.bak``
      before each overwrite so a corrupted save is recoverable.
"""

from __future__ import annotations

import ctypes
import errno
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.exporters.obsidian.errors import (
    ExportError,
    ManifestLockedError,
    ValidationError,
)
from app.exporters.obsidian.types import ManifestEntry


# Schema constants.
MANIFEST_SCHEMA = 1
MANIFEST_VERSION = 1
DEFAULT_STALE_LOCK_SECONDS = 3600

# Layout under vault_root.
_BIFROST_DIR = "Bifrost"
_META_DIR = "_meta"
_MANIFEST_FILENAME = "manifest.json"
_BACKUP_FILENAME = "manifest.json.bak"
_LOCK_FILENAME = ".lock"

# Manifest key shape, e.g. "firm-1234".
_KEY_RE = re.compile(r"^[a-z]+-\d+$")


class ManifestManager:
    """Single-process owner of the exporter manifest and run lock.

    Not thread-safe; the exporter is single-writer by contract.
    """

    def __init__(
        self,
        vault_root: str | Path,
        *,
        stale_lock_seconds: int = DEFAULT_STALE_LOCK_SECONDS,
    ) -> None:
        self._vault_root = Path(vault_root)
        self._meta_dir = self._vault_root / _BIFROST_DIR / _META_DIR
        self._manifest_path = self._meta_dir / _MANIFEST_FILENAME
        self._backup_path = self._meta_dir / _BACKUP_FILENAME
        self._lock_path = self._meta_dir / _LOCK_FILENAME
        self._stale_lock_seconds = stale_lock_seconds

        self._data: dict[str, Any] | None = None
        self._lock_held = False

    # ------------------------------------------------------------------
    # manifest IO
    # ------------------------------------------------------------------

    def load_manifest(self) -> dict[str, Any]:
        """Load the manifest into memory (idempotent).

        If the file is missing, an empty manifest skeleton is returned.
        If the file is corrupt, the backup is tried before giving up.
        """
        if self._data is not None:
            return self._data

        if not self._manifest_path.exists():
            self._data = self._fresh_manifest()
            return self._data

        data = self._read_json_or_none(self._manifest_path)
        if data is None:
            data = self._read_json_or_none(self._backup_path)
            if data is None:
                raise ExportError(
                    f"manifest is unreadable and no usable backup found: "
                    f"{self._manifest_path}"
                )

        self._validate_manifest(data)
        self._data = data
        return self._data

    def save_manifest(self) -> None:
        """Atomically persist the in-memory manifest.

        Sequence:
            1. Copy current on-disk manifest → ``manifest.json.bak``.
            2. Write new payload to ``manifest.json.<rand>.tmp``.
            3. ``fsync`` the temp file.
            4. ``os.replace`` the temp file over ``manifest.json``.
            5. ``fsync`` the parent directory (POSIX only).
        """
        if self._data is None:
            return  # nothing loaded → nothing to write

        self._ensure_meta_dir()
        self._backup_existing_manifest()

        payload = json.dumps(
            self._data,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")

        fd, tmp_name = tempfile.mkstemp(
            prefix="manifest.",
            suffix=".tmp",
            dir=str(self._meta_dir),
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, self._manifest_path)
        except OSError as exc:
            self._unlink_quietly(tmp_path)
            raise ExportError(f"failed to write manifest: {exc}") from exc

        self._fsync_dir(self._meta_dir)

    # ------------------------------------------------------------------
    # lock
    # ------------------------------------------------------------------

    def acquire_lock(self) -> None:
        """Acquire the exporter run lock.

        Atomically creates the lock file via ``O_CREAT | O_EXCL`` and
        writes ``{pid, timestamp}`` JSON inside. If the lock already
        exists it is checked for staleness — if the holder PID is dead
        OR the timestamp is older than ``stale_lock_seconds``, the lock
        is stolen exactly once and acquisition is retried.

        Raises:
            ManifestLockedError: if a live, non-stale lock is held.
            ExportError: on filesystem failures unrelated to contention.
        """
        self._ensure_meta_dir()

        # At most one stale-lock recovery attempt — guards against
        # tight loops if two processes race to steal the same lock.
        for attempt in (0, 1):
            try:
                fd = os.open(
                    self._lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o644,
                )
            except FileExistsError:
                if attempt == 0 and self._is_lock_stale():
                    self._unlink_quietly(self._lock_path)
                    continue
                raise ManifestLockedError(
                    f"manifest lock held: "
                    f"{self._read_lock_payload() or '<unreadable>'}"
                )
            except OSError as exc:
                raise ExportError(
                    f"failed to create lock file at {self._lock_path}: {exc}"
                ) from exc

            payload = json.dumps(
                {
                    "pid": os.getpid(),
                    "timestamp": _utcnow().isoformat(),
                    "host": _hostname(),
                }
            ).encode("utf-8")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(payload)
                    fh.flush()
                    os.fsync(fh.fileno())
            except OSError as exc:
                self._unlink_quietly(self._lock_path)
                raise ExportError(f"failed to write lock file: {exc}") from exc

            self._lock_held = True
            return

        # Unreachable in normal flow — kept as defensive bail-out.
        raise ManifestLockedError(
            "could not acquire lock after stale-lock recovery"
        )

    def release_lock(self) -> None:
        """Release the lock if held. Safe to call unconditionally."""
        if not self._lock_held:
            return
        self._unlink_quietly(self._lock_path)
        self._lock_held = False

    # ------------------------------------------------------------------
    # entry-level operations (in-memory)
    # ------------------------------------------------------------------

    def get_entry(self, key: str) -> Optional[ManifestEntry]:
        self._validate_key(key)
        entries = self._entries()
        raw = entries.get(key)
        if raw is None:
            return None
        return self._entry_from_dict(raw)

    def upsert_entry(self, key: str, entry: ManifestEntry) -> None:
        self._validate_key(key)
        self._entries()[key] = self._entry_to_dict(entry)

    def mark_archived(self, key: str) -> None:
        """Flag an existing entry as archived (soft-deleted in Bifrost).

        Raises ValidationError if the key is unknown — callers should
        ``upsert_entry`` first if they're tracking a brand-new archive.
        """
        self._validate_key(key)
        entries = self._entries()
        raw = entries.get(key)
        if raw is None:
            raise ValidationError(
                f"cannot mark archived: no manifest entry for {key!r}"
            )
        raw["archived"] = True
        if not raw.get("deleted_at"):
            raw["deleted_at"] = _utcnow().isoformat()

    def remove_entry(self, key: str) -> None:
        self._validate_key(key)
        self._entries().pop(key, None)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _entries(self) -> dict[str, Any]:
        data = self.load_manifest()
        return data["entries"]

    def _ensure_meta_dir(self) -> None:
        try:
            self._meta_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ExportError(
                f"failed to create meta directory {self._meta_dir}: {exc}"
            ) from exc

    def _backup_existing_manifest(self) -> None:
        if not self._manifest_path.exists():
            return
        try:
            data = self._manifest_path.read_bytes()
        except OSError as exc:
            raise ExportError(
                f"failed to read manifest for backup: {exc}"
            ) from exc

        tmp_backup = self._backup_path.with_suffix(
            self._backup_path.suffix + ".tmp"
        )
        try:
            with open(tmp_backup, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_backup, self._backup_path)
        except OSError as exc:
            self._unlink_quietly(tmp_backup)
            raise ExportError(f"failed to write manifest backup: {exc}") from exc

    def _is_lock_stale(self) -> bool:
        payload = self._read_lock_payload()
        if payload is None:
            # Unreadable / corrupt → treat as stale so we don't deadlock
            # on garbage left behind by a crashed process.
            return True

        # Timestamp check.
        ts_raw = payload.get("timestamp")
        try:
            ts = datetime.fromisoformat(ts_raw) if isinstance(ts_raw, str) else None
        except ValueError:
            ts = None
        if ts is None:
            return True
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (_utcnow() - ts).total_seconds()
        if age > self._stale_lock_seconds:
            return True

        # PID check (host-aware).
        pid = payload.get("pid")
        host = payload.get("host")
        if not isinstance(pid, int) or pid <= 0:
            return True
        # If the lock was taken on a different host, we cannot probe
        # the PID — fall back to the timestamp check we already did.
        if isinstance(host, str) and host and host != _hostname():
            return False
        return not _pid_alive(pid)

    def _read_lock_payload(self) -> Optional[dict[str, Any]]:
        return self._read_json_or_none(self._lock_path)

    @staticmethod
    def _read_json_or_none(path: Path) -> Optional[dict[str, Any]]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        except OSError:
            return None
        if not isinstance(data, dict):
            return None
        return data

    @staticmethod
    def _unlink_quietly(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        # Directory fsync is a POSIX construct; on Windows it's a no-op
        # and ``os.open`` on a directory is not supported.
        if sys.platform == "win32":
            return
        try:
            dir_fd = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(dir_fd)
        except OSError:
            pass
        finally:
            try:
                os.close(dir_fd)
            except OSError:
                pass

    @staticmethod
    def _validate_key(key: str) -> None:
        if not isinstance(key, str) or not _KEY_RE.match(key):
            raise ValidationError(f"invalid manifest key: {key!r}")

    @staticmethod
    def _validate_manifest(data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValidationError("manifest root must be a JSON object")

        schema = data.get("schema")
        if schema != MANIFEST_SCHEMA:
            if isinstance(schema, int) and schema > MANIFEST_SCHEMA:
                raise ValidationError(
                    f"manifest schema {schema} newer than supported "
                    f"{MANIFEST_SCHEMA}; refusing to load"
                )
            raise ValidationError(f"manifest schema unrecognized: {schema!r}")

        if not isinstance(data.get("entries"), dict):
            raise ValidationError("manifest.entries must be an object")
        if not isinstance(data.get("meta"), dict):
            raise ValidationError("manifest.meta must be an object")

    @staticmethod
    def _fresh_manifest() -> dict[str, Any]:
        return {
            "schema": MANIFEST_SCHEMA,
            "manifest_version": MANIFEST_VERSION,
            "meta": {
                "last_export_at": {},
                "last_full_export_at": None,
                "last_reconcile_at": None,
            },
            "entries": {},
        }

    @staticmethod
    def _entry_to_dict(entry: ManifestEntry) -> dict[str, Any]:
        return {
            "path": entry.path,
            "content_hash": entry.content_hash,
            "schema_version": entry.schema_version,
            "exported_at": _isoformat(entry.exported_at),
            "deleted_at": _isoformat(entry.deleted_at) if entry.deleted_at else None,
            "archived": bool(entry.archived),
        }

    @staticmethod
    def _entry_from_dict(raw: dict[str, Any]) -> ManifestEntry:
        try:
            deleted_at_raw = raw.get("deleted_at")
            return ManifestEntry(
                path=str(raw["path"]),
                content_hash=str(raw["content_hash"]),
                schema_version=int(raw["schema_version"]),
                exported_at=_parse_iso(raw["exported_at"]),
                deleted_at=_parse_iso(deleted_at_raw) if deleted_at_raw else None,
                archived=bool(raw.get("archived", False)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"malformed manifest entry: {exc}") from exc


# ----------------------------------------------------------------------
# module-level helpers
# ----------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_iso(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"expected ISO-8601 string, got {type(value).__name__}")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _hostname() -> str:
    # ``os.uname`` is missing on Windows; ``socket.gethostname`` works
    # everywhere but we prefer to avoid the import unless needed.
    try:
        import socket
        return socket.gethostname()
    except OSError:
        return ""


def _pid_alive(pid: int) -> bool:
    """Return True if a process with ``pid`` exists on this host."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _pid_alive_windows(pid)
    return _pid_alive_posix(pid)


def _pid_alive_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but is owned by another user.
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        return True
    return True


def _pid_alive_windows(pid: int) -> bool:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return True

    handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, ctypes.c_ulong(pid)
    )
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        if not ok:
            return True
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)
