"""Embedding provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Embeds a list of texts into fixed-dim float vectors."""

    name: str = "abstract"
    dim: int = 1536

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:  # pragma: no cover
        ...

    def embed_one(self, text: str) -> List[float]:
        result = self.embed([text])
        return result[0] if result else [0.0] * self.dim
