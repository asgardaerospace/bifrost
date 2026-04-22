"""Intelligence OS schemas — external intel items, classification, actions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from app.schemas.base import ORMModel


IntelCategory = Literal[
    "vc_funding",
    "defense_tech",
    "space_systems",
    "aerospace_manufacturing",
    "supply_chain",
    "policy_procurement",
    "competitor_move",
    "partner_signal",
    "supplier_signal",
    "uncategorized",
]

IntelActionStatus = Literal[
    "pending", "acknowledged", "resolved", "dismissed"
]


# --- primitives -------------------------------------------------------------


class IntelEntityRead(ORMModel):
    id: int
    intel_item_id: int
    entity_type: str
    entity_name: str
    entity_id: Optional[int] = None
    role: Optional[str] = None
    created_at: datetime


class IntelTagRead(ORMModel):
    id: int
    intel_item_id: int
    tag: str
    created_at: datetime


class IntelActionRead(ORMModel):
    id: int
    intel_item_id: int
    action_type: str
    recommended_action: str
    status: IntelActionStatus
    created_at: datetime
    updated_at: datetime


# --- items ------------------------------------------------------------------


class IntelItemRead(ORMModel):
    id: int
    source: str
    title: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    region: Optional[str] = None
    category: IntelCategory
    summary: Optional[str] = None
    strategic_relevance_score: int
    urgency_score: int
    confidence_score: int
    created_at: datetime
    updated_at: datetime

    entities: list[IntelEntityRead] = []
    tags: list[IntelTagRead] = []
    actions: list[IntelActionRead] = []


class IntelItemCreate(ORMModel):
    """Shape the ingestion layer produces before classification.

    Classification fills category, scores, tags, and actions. Ingestion
    is responsible for source provenance (source, url, published_at)
    and raw content (title, summary, region).
    """

    source: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=512)
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    region: Optional[str] = None
    summary: Optional[str] = None
    # Optional raw entity hints a provider already extracted.
    raw_entities: list["IntelRawEntityHint"] = []


class IntelRawEntityHint(ORMModel):
    entity_type: str
    entity_name: str
    role: Optional[str] = None


IntelItemCreate.model_rebuild()


# --- aggregations -----------------------------------------------------------


class IntelTopSignals(ORMModel):
    generated_at: datetime
    total: int
    items: list[IntelItemRead]


class IntelCategoryBucket(ORMModel):
    category: IntelCategory
    count: int
    items: list[IntelItemRead] = []


class IntelByCategory(ORMModel):
    generated_at: datetime
    total: int
    categories: list[IntelCategoryBucket]


class IntelRegionBucket(ORMModel):
    region: str
    count: int
    items: list[IntelItemRead] = []


class IntelByRegion(ORMModel):
    generated_at: datetime
    total: int
    regions: list[IntelRegionBucket]


class IntelIngestionReport(ORMModel):
    started_at: datetime
    finished_at: datetime
    provider_counts: dict[str, int]
    created: int
    updated: int
    skipped: int
    total_items_seen: int
