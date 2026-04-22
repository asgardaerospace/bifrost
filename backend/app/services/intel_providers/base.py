"""Intel provider protocol.

A provider is a callable that yields IntelItemCreate records. The
protocol is deliberately narrow so providers can wrap anything — RSS
feeds, curated newsletter exports, API pulls, manual CSV dumps — without
coupling the ingestion pipeline to any transport.

Providers MUST:
  - return iterable of IntelItemCreate
  - populate `source` with a stable string (used for dedupe + auditing)
  - never raise for empty results; return [] instead

Providers MAY:
  - populate `raw_entities` with hint rows the classifier will persist
  - populate `region` when the source already knows it

Everything else (category, scores, tags, actions) is the classifier's
job.
"""

from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from app.schemas.intel import IntelItemCreate


@runtime_checkable
class IntelProvider(Protocol):
    name: str

    def fetch(self) -> Iterable[IntelItemCreate]:
        ...
