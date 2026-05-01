"""HTTP surface for the Obsidian exporter.

Wraps the existing :class:`ExporterService` and the read-only
:func:`reconcile_vault` audit. Synchronous handlers — at dev-scale
the full export completes in a few hundred milliseconds. A
background-task variant for long runs lives in the architecture
roadmap but isn't needed yet.

Routes (all under ``/api/v1/obsidian``):
    POST /export/full          run a full export
    POST /export/incremental   run an incremental export (optional ``since``)
    GET  /reconcile            audit vault ↔ manifest drift
    GET  /status               manifest summary + vault path
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.exporters.obsidian.config import (
    ObsidianExportSettings,
    get_obsidian_settings,
)
from app.exporters.obsidian.errors import (
    ExportError,
    ManifestLockedError,
    ValidationError,
)
from app.exporters.obsidian.manifest import ManifestManager
from app.exporters.obsidian.reconciler import reconcile_vault
from app.exporters.obsidian.service import ExporterService

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/obsidian", tags=["obsidian"])


# ----------------------------------------------------------------------
# dependencies
# ----------------------------------------------------------------------


def _settings_dep() -> ObsidianExportSettings:
    try:
        return get_obsidian_settings()
    except Exception as exc:  # noqa: BLE001 — pydantic ValidationError, etc.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"obsidian settings invalid: {exc}",
        )


def _service_dep(
    db: Session = Depends(get_db),
    settings: ObsidianExportSettings = Depends(_settings_dep),
) -> ExporterService:
    """Build a per-request :class:`ExporterService` that reuses the
    request-scoped DB session via a thin factory closure.

    Closing the session twice (once by the service's ``finally``, once
    by ``get_db``) is harmless — SQLAlchemy's ``Session.close`` is
    idempotent. We accept that minor redundancy in exchange for
    honoring the request lifecycle.
    """
    return ExporterService(
        settings=settings,
        session_factory=lambda: db,
    )


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _exec_export(call) -> dict[str, Any]:
    """Run an export callable and translate exporter errors into HTTP."""
    try:
        results = call()
    except ManifestLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"another export run holds the lock: {exc}",
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except ExportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return {
        entity_type: asdict(result) for entity_type, result in results.items()
    }


def _parse_since(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid 'since' value: {exc}",
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ----------------------------------------------------------------------
# routes
# ----------------------------------------------------------------------


@router.post("/export/full")
def export_full(
    service: ExporterService = Depends(_service_dep),
) -> dict[str, Any]:
    return _exec_export(service.run_full)


@router.post("/export/incremental")
def export_incremental(
    since: Optional[str] = Body(default=None, embed=True),
    service: ExporterService = Depends(_service_dep),
) -> dict[str, Any]:
    parsed_since = _parse_since(since)
    return _exec_export(lambda: service.run_incremental(since=parsed_since))


@router.get("/reconcile")
def reconcile(
    settings: ObsidianExportSettings = Depends(_settings_dep),
) -> dict[str, Any]:
    try:
        report = reconcile_vault(settings.vault_root)
    except (ValidationError, ExportError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    return report.to_dict()


@router.get("/status")
def export_status(
    settings: ObsidianExportSettings = Depends(_settings_dep),
) -> dict[str, Any]:
    try:
        manifest = ManifestManager(settings.vault_root)
        data = manifest.load_manifest()
    except (ValidationError, ExportError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    entries = data.get("entries", {}) or {}
    meta = data.get("meta", {}) or {}

    return {
        "vault_root": settings.vault_root,
        "export_enabled": settings.export_enabled,
        "total_files": len(entries),
        "last_export_at": meta.get("last_export_at", {}) or {},
        "last_full_export_at": meta.get("last_full_export_at"),
        "last_reconcile_at": meta.get("last_reconcile_at"),
    }
