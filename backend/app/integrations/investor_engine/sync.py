"""Read-only ingestion from the investor engine into Bifrost.

Flow:

    client.fetch_payload()
        -> EnginePayload (validated)
        -> mapper.map_investor(...)
        -> NormalizedInvestor
        -> upsert into investor_engine_snapshots

The sync never writes to Bifrost's core investor tables. It only
populates the snapshot cache, keyed by `external_id`. This is what
keeps the integration non-destructive while still letting the rest of
Bifrost (dashboard, command console, investor execution views) read
engine-sourced data through the usual service layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.investor_engine import mapper
from app.integrations.investor_engine.client import (
    InvestorEngineClient,
    get_default_client,
)
from app.integrations.investor_engine.models import InvestorEngineSnapshot
from app.integrations.investor_engine.schemas import EngineInvestor


@dataclass
class SyncReport:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
        }


def _upsert_one(db: Session, engine_inv: EngineInvestor) -> str:
    normalized = mapper.map_investor(engine_inv)
    existing = db.execute(
        select(InvestorEngineSnapshot).where(
            InvestorEngineSnapshot.external_id == normalized.external_id
        )
    ).scalar_one_or_none()

    payload_dict = normalized.model_dump(mode="json")
    now = datetime.now(timezone.utc)

    if existing is None:
        db.add(
            InvestorEngineSnapshot(
                external_id=normalized.external_id,
                firm_name=normalized.firm_name,
                stage=normalized.stage,
                follow_up_status=normalized.follow_up_status,
                last_touch_at=normalized.last_touch_at,
                next_follow_up_at=normalized.next_follow_up_at,
                next_step=normalized.next_step,
                owner=normalized.owner,
                payload=payload_dict,
                engine_updated_at=normalized.engine_updated_at,
                synced_at=now,
            )
        )
        return "created"

    if (
        existing.engine_updated_at
        and normalized.engine_updated_at
        and existing.engine_updated_at >= normalized.engine_updated_at
        and existing.payload == payload_dict
    ):
        return "unchanged"

    existing.firm_name = normalized.firm_name
    existing.stage = normalized.stage
    existing.follow_up_status = normalized.follow_up_status
    existing.last_touch_at = normalized.last_touch_at
    existing.next_follow_up_at = normalized.next_follow_up_at
    existing.next_step = normalized.next_step
    existing.owner = normalized.owner
    existing.payload = payload_dict
    existing.engine_updated_at = normalized.engine_updated_at
    existing.synced_at = now
    return "updated"


def run_sync(
    db: Session,
    client: Optional[InvestorEngineClient] = None,
) -> SyncReport:
    """Pull the full engine payload and upsert the snapshot cache."""
    client = client or get_default_client()
    payload = client.fetch_payload()
    report = SyncReport(fetched=len(payload.investors))

    for inv in payload.investors:
        outcome = _upsert_one(db, inv)
        if outcome == "created":
            report.created += 1
        elif outcome == "updated":
            report.updated += 1
        else:
            report.unchanged += 1

    db.commit()
    return report
