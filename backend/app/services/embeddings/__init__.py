"""Embedding provider factory.

Selection (env): EMBEDDING_PROVIDER=local|openai (default: local).
The OpenAI provider is lazy-imported and requires OPENAI_API_KEY. The local
provider has no external dependencies and is deterministic — suitable for
tests, offline dev, and as a permanent fallback.
"""

from __future__ import annotations

import os
from functools import lru_cache

from .base import EmbeddingProvider
from .local import LocalHashEmbeddingProvider


@lru_cache(maxsize=1)
def get_provider() -> EmbeddingProvider:
    name = (os.environ.get("EMBEDDING_PROVIDER") or "local").lower()
    if name == "openai":
        try:
            from .openai_provider import OpenAIEmbeddingProvider

            return OpenAIEmbeddingProvider()
        except Exception:
            # Fall back silently — log via stdlib so ops can see the downgrade.
            import logging

            logging.getLogger(__name__).warning(
                "openai embedding provider unavailable; falling back to local"
            )
            return LocalHashEmbeddingProvider()
    return LocalHashEmbeddingProvider()


__all__ = ["EmbeddingProvider", "get_provider"]
