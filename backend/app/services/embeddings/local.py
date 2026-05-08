"""Deterministic local embedding provider.

Strategy: token-bucket bag-of-tokens with stable hashing. Each text is
normalized, tokenized on word boundaries, and each token is hashed into one
of `dim` buckets. The resulting count vector is L2-normalized for cosine
similarity. This produces meaningful semantic-ish similarity for tests
(token-overlap based) and is fully deterministic across runs and machines.

Not a substitute for a real model — but good enough to validate the
retrieval ranking, RAG assembly, and citation extraction pipelines without
external API dependencies.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import List

from .base import EmbeddingProvider


_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN.findall((text or "").lower())


def _bucket(token: str, dim: int) -> int:
    h = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") % dim


class LocalHashEmbeddingProvider(EmbeddingProvider):
    name = "local-hash-bow-v1"
    dim = 1536

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for tok in _tokenize(text):
            # Spread mass across two buckets per token so tiny vocabularies
            # don't collapse to identical sparse vectors.
            for salt in (tok, tok + "$"):
                vec[_bucket(salt, self.dim)] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
