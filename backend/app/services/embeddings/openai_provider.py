"""OpenAI embedding provider — text-embedding-3-small (1536 dim).

Lazy-imports the openai package; raises ImportError if not installed. Reads
OPENAI_API_KEY from env. No retry/backoff in Sprint 3 — failures bubble up
and the calling pipeline marks the affected memory record as
embedding_status='failed' with a retry timestamp.
"""

from __future__ import annotations

import os
from typing import List

from .base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai/text-embedding-3-small"
    dim = 1536
    model = "text-embedding-3-small"

    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set; cannot use OpenAI embedding provider"
            )
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise ImportError(
                "openai package not installed; pip install openai"
            ) from e
        self._client = OpenAI(api_key=api_key)

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # OpenAI accepts a batched call; chunked at 96 inputs per request to
        # keep per-call latency bounded.
        results: List[List[float]] = []
        for i in range(0, len(texts), 96):
            batch = texts[i : i + 96]
            resp = self._client.embeddings.create(model=self.model, input=batch)
            results.extend(d.embedding for d in resp.data)
        return results
