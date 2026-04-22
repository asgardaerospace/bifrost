"""Seed intel provider.

Ships a curated fixture of realistic aerospace/defense/VC signals so the
Intelligence OS pipeline can be exercised end-to-end without any
external network dependency. Safe to re-run — the ingestion service
dedupes by (source, url).

When real providers (RSS, API pulls) are added later, they follow the
same IntelProvider protocol; this fixture need not change.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.schemas.intel import IntelItemCreate, IntelRawEntityHint


def _hours_ago(n: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=n)


def _days_ago(n: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n)


class SeedProvider:
    name = "seed"

    def fetch(self) -> Iterable[IntelItemCreate]:
        return [
            IntelItemCreate(
                source="seed",
                title=(
                    "Shield AI raises $500M Series F led by Hanwha and Andreessen "
                    "Horowitz to scale autonomy for defense"
                ),
                url="https://example.com/intel/shield-ai-series-f",
                published_at=_hours_ago(6),
                region="US",
                summary=(
                    "Shield AI closed a $500M Series F round at a $5B valuation. "
                    "Capital will fund expansion of V-BAT production and autonomy "
                    "stack deployment across DoD programs."
                ),
                raw_entities=[
                    IntelRawEntityHint(
                        entity_type="company", entity_name="Shield AI", role="investee"
                    ),
                    IntelRawEntityHint(
                        entity_type="investor",
                        entity_name="Andreessen Horowitz",
                        role="investor",
                    ),
                    IntelRawEntityHint(
                        entity_type="investor",
                        entity_name="Hanwha",
                        role="investor",
                    ),
                ],
            ),
            IntelItemCreate(
                source="seed",
                title=(
                    "Anduril acquires Blue Force Technologies to expand unmanned "
                    "fighter program"
                ),
                url="https://example.com/intel/anduril-blue-force",
                published_at=_days_ago(1.5),
                region="US",
                summary=(
                    "Anduril announced the acquisition of Blue Force Technologies, "
                    "a stealth UAV startup, to accelerate its Fury autonomous "
                    "fighter under the DoD CCA program."
                ),
                raw_entities=[
                    IntelRawEntityHint(
                        entity_type="company",
                        entity_name="Anduril",
                        role="acquirer",
                    ),
                    IntelRawEntityHint(
                        entity_type="company",
                        entity_name="Blue Force Technologies",
                        role="acquiree",
                    ),
                    IntelRawEntityHint(
                        entity_type="program",
                        entity_name="CCA",
                        role="mentioned",
                    ),
                ],
            ),
            IntelItemCreate(
                source="seed",
                title=(
                    "Space Force awards $700M launch services contract to SpaceX "
                    "and ULA under NSSL Phase 3"
                ),
                url="https://example.com/intel/nssl-phase3",
                published_at=_hours_ago(30),
                region="US",
                summary=(
                    "The US Space Force awarded combined $700M in launch services "
                    "under NSSL Phase 3, split between SpaceX and ULA. Additional "
                    "on-ramp slots will open for new entrants next fiscal year."
                ),
                raw_entities=[
                    IntelRawEntityHint(
                        entity_type="agency",
                        entity_name="Space Force",
                        role="customer",
                    ),
                    IntelRawEntityHint(
                        entity_type="company", entity_name="SpaceX", role="primary"
                    ),
                    IntelRawEntityHint(
                        entity_type="company", entity_name="ULA", role="primary"
                    ),
                ],
            ),
            IntelItemCreate(
                source="seed",
                title=(
                    "Titanium supply chain disruption: export ban threatens "
                    "aerospace Tier 1 suppliers"
                ),
                url="https://example.com/intel/titanium-export-ban",
                published_at=_hours_ago(12),
                region="Global",
                summary=(
                    "A new export ban on aerospace-grade titanium is expected to "
                    "disrupt Tier 1 supplier inventories within 60 days, with "
                    "Boeing, Airbus, and Lockheed exposed."
                ),
                raw_entities=[
                    IntelRawEntityHint(
                        entity_type="company", entity_name="Boeing", role="mentioned"
                    ),
                    IntelRawEntityHint(
                        entity_type="company", entity_name="Airbus", role="mentioned"
                    ),
                    IntelRawEntityHint(
                        entity_type="company",
                        entity_name="Lockheed",
                        role="mentioned",
                    ),
                ],
            ),
            IntelItemCreate(
                source="seed",
                title=(
                    "DARPA issues RFI for hypersonic propulsion ground test "
                    "infrastructure"
                ),
                url="https://example.com/intel/darpa-hypersonic-rfi",
                published_at=_days_ago(3),
                region="US",
                summary=(
                    "DARPA issued an RFI seeking industry partners for a new "
                    "hypersonic ground test facility. Responses due in 45 days."
                ),
                raw_entities=[
                    IntelRawEntityHint(
                        entity_type="agency", entity_name="DARPA", role="customer"
                    ),
                ],
            ),
            IntelItemCreate(
                source="seed",
                title=(
                    "Rocket Lab and Airbus announce teaming agreement on European "
                    "launch services"
                ),
                url="https://example.com/intel/rocket-lab-airbus-teaming",
                published_at=_days_ago(4),
                region="Europe",
                summary=(
                    "Rocket Lab and Airbus signed a teaming agreement covering "
                    "responsive launch from European ranges. Joint venture "
                    "formation is under consideration."
                ),
                raw_entities=[
                    IntelRawEntityHint(
                        entity_type="company",
                        entity_name="Rocket Lab",
                        role="partner",
                    ),
                    IntelRawEntityHint(
                        entity_type="company", entity_name="Airbus", role="partner"
                    ),
                ],
            ),
            IntelItemCreate(
                source="seed",
                title=(
                    "GAO report flags procurement delays in Next Generation "
                    "Interceptor program"
                ),
                url="https://example.com/intel/gao-ngi-delays",
                published_at=_days_ago(6),
                region="US",
                summary=(
                    "The GAO published a report detailing schedule slip and "
                    "cost growth in the Next Generation Interceptor program, "
                    "including supplier readiness concerns."
                ),
                raw_entities=[
                    IntelRawEntityHint(
                        entity_type="agency", entity_name="GAO", role="regulator"
                    ),
                    IntelRawEntityHint(
                        entity_type="program", entity_name="NGI", role="mentioned"
                    ),
                ],
            ),
            IntelItemCreate(
                source="seed",
                title=(
                    "Palantir wins $480M Army TITAN contract expansion"
                ),
                url="https://example.com/intel/palantir-titan-expansion",
                published_at=_days_ago(2.2),
                region="US",
                summary=(
                    "The US Army expanded its TITAN program award with Palantir "
                    "by $480M to cover additional ground station deliveries."
                ),
                raw_entities=[
                    IntelRawEntityHint(
                        entity_type="company",
                        entity_name="Palantir",
                        role="primary",
                    ),
                    IntelRawEntityHint(
                        entity_type="agency",
                        entity_name="US Army",
                        role="customer",
                    ),
                ],
            ),
            IntelItemCreate(
                source="seed",
                title=(
                    "Mach Industries closes $85M Series B for defense hardware "
                    "manufacturing"
                ),
                url="https://example.com/intel/mach-series-b",
                published_at=_days_ago(8),
                region="US",
                summary=(
                    "Mach Industries raised $85M in a Series B round led by "
                    "Sequoia, with participation from Bedrock and Khosla. "
                    "Focus areas: propulsion and aerostructures."
                ),
                raw_entities=[
                    IntelRawEntityHint(
                        entity_type="company",
                        entity_name="Mach Industries",
                        role="investee",
                    ),
                    IntelRawEntityHint(
                        entity_type="investor", entity_name="Sequoia", role="investor"
                    ),
                    IntelRawEntityHint(
                        entity_type="investor", entity_name="Bedrock", role="investor"
                    ),
                ],
            ),
            IntelItemCreate(
                source="seed",
                title=(
                    "EU adopts new defense procurement framework emphasizing "
                    "strategic autonomy"
                ),
                url="https://example.com/intel/eu-edf-framework",
                published_at=_days_ago(5),
                region="Europe",
                summary=(
                    "The European Commission adopted a new defense procurement "
                    "framework that prioritizes domestic suppliers and "
                    "strategic autonomy for critical components."
                ),
                raw_entities=[
                    IntelRawEntityHint(
                        entity_type="agency",
                        entity_name="European Commission",
                        role="regulator",
                    ),
                ],
            ),
        ]
