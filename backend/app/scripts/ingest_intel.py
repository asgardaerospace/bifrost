"""Intelligence OS ingestion entry point.

Run with:
    python -m app.scripts.ingest_intel

Pulls from every provider registered in app.services.intel_providers.REGISTRY,
classifies each item, and persists the results. Safe to rerun — dedupes on
(source, url).
"""
from __future__ import annotations

from app.core.database import SessionLocal
from app.services import intel as intel_service


def main() -> None:
    db = SessionLocal()
    try:
        report = intel_service.ingest_from_providers(db, actor="cli")
        print("Intel ingestion complete.")
        print(f"  started:  {report.started_at.isoformat()}")
        print(f"  finished: {report.finished_at.isoformat()}")
        print(f"  seen:     {report.total_items_seen}")
        print(f"  created:  {report.created}")
        print(f"  updated:  {report.updated}")
        print(f"  skipped:  {report.skipped}")
        for provider, count in report.provider_counts.items():
            print(f"    - {provider}: {count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
