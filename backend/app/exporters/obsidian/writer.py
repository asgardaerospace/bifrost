"""Filesystem layer for the Obsidian exporter.

All bytes that touch the vault flow through :class:`FileWriter`. The
class enforces three invariants:

    1. Every write is atomic: write to ``.tmp`` in the destination
       directory, ``fsync`` the file, then ``os.replace`` it over the
       target. A crash mid-write leaves either the old or the new file,
       never a half-written one.

    2. Every path is contained inside ``{vault_root}/Bifrost``. Symlink
       traversal, ``..``, and absolute paths pointing elsewhere are all
       rejected.

    3. Every markdown filename matches ``^[a-z]+-\\d+\\.md$``. Live tree
       and ``_archive/`` mirror tree both follow this rule. The
       ``_meta/`` subtree is owned by :class:`ManifestManager` and is
       off-limits to this writer.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Literal

from app.exporters.obsidian.errors import ExportError, ValidationError


_BIFROST_DIR = "Bifrost"
_ARCHIVE_DIR = "_archive"
_META_DIR = "_meta"

# Markdown filename contract: prefix-id.md, all lowercase ASCII.
_FILENAME_RE = re.compile(r"^[a-z]+-\d+\.md$")

_PathClass = Literal["live", "archive", "meta", "root"]


class FileWriter:
    """Atomic, contained writer for note files under the Bifrost vault."""

    def __init__(self, vault_root: str | Path) -> None:
        self._vault_root = Path(vault_root)
        self._bifrost_root = (self._vault_root / _BIFROST_DIR).resolve(strict=False)
        self._archive_root = self._bifrost_root / _ARCHIVE_DIR
        self._meta_root = self._bifrost_root / _META_DIR

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def write_atomic(self, path: str | Path, content: str | bytes) -> None:
        target = self._validate_note_path(path, expect="live")
        data = self._encode(content)
        self._ensure_parent(target)
        self._atomic_write_bytes(target, data)

    def archive_file(
        self,
        src_path: str | Path,
        archive_path: str | Path,
    ) -> None:
        src = self._validate_note_path(src_path, expect="live")
        dst = self._validate_note_path(archive_path, expect="archive")
        self._require_same_filename(src, dst)

        if not src.exists():
            raise ExportError(f"cannot archive: source missing: {src}")

        self._ensure_parent(dst)
        self._atomic_move(src, dst)

    def restore_file(
        self,
        archive_path: str | Path,
        dest_path: str | Path,
    ) -> None:
        src = self._validate_note_path(archive_path, expect="archive")
        dst = self._validate_note_path(dest_path, expect="live")
        self._require_same_filename(src, dst)

        if not src.exists():
            raise ExportError(f"cannot restore: archive missing: {src}")

        self._ensure_parent(dst)
        self._atomic_move(src, dst)

    # ------------------------------------------------------------------
    # path validation
    # ------------------------------------------------------------------

    def _validate_note_path(
        self,
        path: str | Path,
        *,
        expect: Literal["live", "archive"],
    ) -> Path:
        if not isinstance(path, (str, Path)):
            raise ValidationError(
                f"path must be str or Path, got {type(path).__name__}"
            )

        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self._vault_root / candidate

        try:
            resolved = candidate.resolve(strict=False)
        except OSError as exc:
            raise ValidationError(f"failed to resolve path {candidate}: {exc}") from exc

        if not _is_within(resolved, self._bifrost_root):
            raise ValidationError(
                f"path escapes Bifrost vault namespace: {resolved}"
            )

        klass = self._classify(resolved)

        if klass == "meta":
            raise ValidationError(
                f"FileWriter cannot write under _meta/: {resolved}"
            )
        if klass == "root":
            raise ValidationError(
                f"path must be a file under Bifrost/, not the root: {resolved}"
            )
        if expect == "live" and klass != "live":
            raise ValidationError(
                f"expected a live-tree path, got {klass}: {resolved}"
            )
        if expect == "archive" and klass != "archive":
            raise ValidationError(
                f"expected an _archive/ path, got {klass}: {resolved}"
            )

        if not _FILENAME_RE.match(resolved.name):
            raise ValidationError(
                f"filename does not match {_FILENAME_RE.pattern!r}: "
                f"{resolved.name}"
            )

        return resolved

    def _classify(self, resolved: Path) -> _PathClass:
        try:
            rel = resolved.relative_to(self._bifrost_root)
        except ValueError:
            raise ValidationError(f"path is not under Bifrost root: {resolved}")
        parts = rel.parts
        if not parts:
            return "root"
        first = parts[0]
        if first == _META_DIR:
            return "meta"
        if first == _ARCHIVE_DIR:
            return "archive"
        return "live"

    @staticmethod
    def _require_same_filename(src: Path, dst: Path) -> None:
        if src.name != dst.name:
            raise ValidationError(
                f"archive/restore filename mismatch: "
                f"src={src.name!r} dst={dst.name!r}"
            )

    # ------------------------------------------------------------------
    # filesystem primitives
    # ------------------------------------------------------------------

    @staticmethod
    def _encode(content: str | bytes) -> bytes:
        if isinstance(content, bytes):
            return content
        if isinstance(content, str):
            normalized = content.replace("\r\n", "\n").replace("\r", "\n")
            return normalized.encode("utf-8")
        raise ValidationError(
            f"unsupported content type: {type(content).__name__}"
        )

    @staticmethod
    def _ensure_parent(path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ExportError(
                f"failed to create directory {path.parent}: {exc}"
            ) from exc

    @classmethod
    def _atomic_write_bytes(cls, target: Path, data: bytes) -> None:
        parent = target.parent
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=str(parent),
            )
        except OSError as exc:
            raise ExportError(
                f"failed to open temp file in {parent}: {exc}"
            ) from exc

        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, target)
        except OSError as exc:
            cls._unlink_quietly(tmp_path)
            raise ExportError(f"failed to write {target}: {exc}") from exc

        cls._fsync_dir(parent)

    @classmethod
    def _atomic_move(cls, src: Path, dst: Path) -> None:
        try:
            os.replace(src, dst)
        except OSError as exc:
            raise ExportError(
                f"failed to move {src} -> {dst}: {exc}"
            ) from exc

        cls._fsync_dir(dst.parent)
        if src.parent != dst.parent:
            cls._fsync_dir(src.parent)

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


# ----------------------------------------------------------------------
# module-level helpers
# ----------------------------------------------------------------------


def _is_within(path: Path, root: Path) -> bool:
    try:
        return path == root or path.is_relative_to(root)
    except ValueError:
        return False
