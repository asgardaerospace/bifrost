"""Intelligence ingestion providers.

Each provider implements the IntelProvider protocol (see base.py) and is
registered in REGISTRY below. The ingestion service iterates all enabled
providers, normalizes the items they yield, and hands them to the
classifier + persistence pipeline.

Providers are intentionally backend-only. No scraping is exposed to
the frontend — the shell reads the already-normalized intel_items table.

Phase 1 ships a SeedProvider (deterministic fixture items) so the stack
is end-to-end testable without network access. To add a real provider,
implement IntelProvider and append it to REGISTRY.
"""

from __future__ import annotations

from app.services.intel_providers.base import IntelProvider
from app.services.intel_providers.seed import SeedProvider

# Order defines ingestion order. Duplicates (same source + url) are
# deduped downstream by the service layer.
REGISTRY: list[IntelProvider] = [
    SeedProvider(),
]

__all__ = ["IntelProvider", "REGISTRY", "SeedProvider"]
