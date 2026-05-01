"""Public entrypoint for the Obsidian exporter."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.exporters.obsidian.config import (
    ObsidianExportSettings,
    get_obsidian_settings,
)
from app.exporters.obsidian.coordinator import SyncCoordinator
from app.exporters.obsidian.errors import ExportError
from app.exporters.obsidian.transformers.base import EntityTransformer
from app.exporters.obsidian.transformers.account import AccountTransformer
from app.exporters.obsidian.transformers.communication import (
    CommunicationTransformer,
)
from app.exporters.obsidian.transformers.investor_contact import (
    InvestorContactTransformer,
)
from app.exporters.obsidian.transformers.intel_item import (
    IntelItemTransformer,
)
from app.exporters.obsidian.transformers.investor_firm import (
    InvestorFirmTransformer,
)
from app.exporters.obsidian.transformers.meeting import MeetingTransformer
from app.exporters.obsidian.transformers.note import NoteTransformer
from app.exporters.obsidian.transformers.program import ProgramTransformer
from app.exporters.obsidian.transformers.supplier import SupplierTransformer
from app.exporters.obsidian.types import ExportResult

logger = logging.getLogger(__name__)


SessionFactory = Callable[[], Session]


def _default_session_factory() -> Session:
    from app.core.database import SessionLocal
    return SessionLocal()


def _default_transformers() -> list[EntityTransformer]:
    # Order matters once parent-touch is wired in: parents first so a
    # full run sees the freshest parent state when child sections embed
    # parent links.
    return [
        InvestorFirmTransformer(),
        InvestorContactTransformer(),
        AccountTransformer(),
        SupplierTransformer(),
        ProgramTransformer(),
        MeetingTransformer(),
        CommunicationTransformer(),
        NoteTransformer(),
        IntelItemTransformer(),
    ]


class ExporterService:
    """Thin facade: configures inputs, hands off to the coordinator."""

    def __init__(
        self,
        settings: ObsidianExportSettings | None = None,
        *,
        session_factory: SessionFactory | None = None,
        transformers: list[EntityTransformer] | None = None,
    ) -> None:
        self._settings = settings or get_obsidian_settings()
        self._session_factory = session_factory or _default_session_factory
        self._transformers = transformers or _default_transformers()

    def run_full(self) -> dict[str, ExportResult]:
        return self._run(mode="full", since=None)

    def run_incremental(
        self, since: datetime | None = None
    ) -> dict[str, ExportResult]:
        return self._run(mode="incremental", since=since)

    def _run(
        self, *, mode: str, since: datetime | None
    ) -> dict[str, ExportResult]:
        if not self._settings.export_enabled:
            raise ExportError(
                "OBSIDIAN_EXPORT_ENABLED is false; refusing to run"
            )

        session = self._session_factory()
        try:
            coordinator = SyncCoordinator(
                vault_root=self._settings.vault_root,
                session=session,
                transformers=self._transformers,
            )
            return coordinator.run(mode=mode, since=since)
        finally:
            try:
                session.close()
            except Exception:  # noqa: BLE001
                logger.exception("failed to close session after export run")
