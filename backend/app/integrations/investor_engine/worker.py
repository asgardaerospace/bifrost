"""Execution worker for pending_engine_writes.

Intentionally simple — no job queue, no scheduler. A caller (cron,
CLI, HTTP POST) invokes `run_once` and we drain a batch of pending
rows. Retries are manual: operators/users re-trigger failed rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.investor_engine import client as engine_client
from app.integrations.investor_engine import writer
from app.integrations.investor_engine.writes_models import (
    PendingEngineWrite,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SUCCEEDED,
)


@dataclass
class WorkerReport:
    picked: int = 0
    succeeded: int = 0
    failed: int = 0
    processed_ids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict[str, int | list[int]]:
        return {
            "picked": self.picked,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "processed_ids": self.processed_ids,
        }


def run_once(
    db: Session,
    *,
    batch_size: int = 25,
    client: Optional[engine_client.InvestorEngineClient] = None,
) -> WorkerReport:
    """Process up to `batch_size` pending writes."""
    rows = list(
        db.execute(
            select(PendingEngineWrite)
            .where(PendingEngineWrite.status == STATUS_PENDING)
            .order_by(PendingEngineWrite.created_at.asc())
            .limit(batch_size)
        ).scalars().all()
    )

    report = WorkerReport(picked=len(rows))
    for row in rows:
        writer.execute_write(db, row, client=client)
        report.processed_ids.append(row.id)
        if row.status == STATUS_SUCCEEDED:
            report.succeeded += 1
        elif row.status == STATUS_FAILED:
            report.failed += 1
    return report


def run_one(
    db: Session,
    write_id: int,
    *,
    client: Optional[engine_client.InvestorEngineClient] = None,
) -> Optional[PendingEngineWrite]:
    """Manually retrigger a specific write (pending or failed)."""
    row = db.get(PendingEngineWrite, write_id)
    if row is None:
        return None
    # Retrying a failed row — move it back to pending so execute_write
    # will run it again (it also accepts STATUS_FAILED directly, but
    # this keeps status transitions clean in the audit log).
    if row.status == STATUS_FAILED:
        row.status = STATUS_PENDING
        db.flush()
        db.commit()
        db.refresh(row)
    return writer.execute_write(db, row, client=client)
