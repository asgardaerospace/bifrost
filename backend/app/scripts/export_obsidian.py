"""CLI entrypoint for the Obsidian exporter.

Usage:
    python -m app.scripts.export_obsidian full
    python -m app.scripts.export_obsidian incremental [--since ISO8601]
    python -m app.scripts.export_obsidian reconcile

Exit codes:
    0  success, no errors / vault clean
    1  success but row-level errors / reconciler found drift
    2  aborted (config invalid, lock held, crash)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime, timezone

from app.exporters.obsidian.config import get_obsidian_settings
from app.exporters.obsidian.errors import (
    ExportError,
    ManifestLockedError,
    ValidationError,
)
from app.exporters.obsidian.reconciler import reconcile_vault
from app.exporters.obsidian.service import ExporterService


_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="export_obsidian",
        description="Export Bifrost data to an Obsidian vault.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("full", help="Re-export every row of every entity type.")

    inc = sub.add_parser(
        "incremental",
        help="Export rows changed since the last successful run.",
    )
    inc.add_argument(
        "--since",
        type=str,
        default=None,
        help="ISO-8601 timestamp; overrides the manifest's last_export_at.",
    )

    sub.add_parser(
        "reconcile",
        help="Audit the vault against the manifest (read-only).",
    )
    return parser


def _parse_since(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"invalid --since value {value!r}: {exc}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=args.log_level, format=_LOG_FORMAT)

    try:
        if args.command == "reconcile":
            return _run_reconcile()

        service = ExporterService()
        if args.command == "full":
            results = service.run_full()
        elif args.command == "incremental":
            results = service.run_incremental(since=_parse_since(args.since))
        else:
            print(f"aborted: unknown command {args.command!r}", file=sys.stderr)
            return 2
    except ManifestLockedError as exc:
        print(f"aborted: another export run holds the lock: {exc}", file=sys.stderr)
        return 2
    except (ValidationError, ExportError) as exc:
        print(f"aborted: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        logging.exception("export crashed")
        print(f"aborted: unexpected error: {exc}", file=sys.stderr)
        return 2

    summary = {
        entity_type: asdict(result)
        for entity_type, result in results.items()
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    total_errors = sum(r.errors for r in results.values())
    return 1 if total_errors else 0


def _run_reconcile() -> int:
    """Read-only vault audit. No DB session, no lock acquisition.

    Settings are loaded for ``vault_root`` only; the ``export_enabled``
    flag is intentionally not consulted here — auditing should remain
    available even when exports are paused.
    """
    try:
        settings = get_obsidian_settings()
        report = reconcile_vault(settings.vault_root)
    except (ValidationError, ExportError) as exc:
        print(f"aborted: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        logging.exception("reconcile crashed")
        print(f"aborted: unexpected error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
