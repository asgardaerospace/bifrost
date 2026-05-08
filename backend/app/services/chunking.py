"""Deterministic text chunking for the memory pipeline.

Splits content into chunks of approximately `target_tokens` tokens with a
small overlap so retrieval has context bridges between chunks. Token count
is approximated by whitespace-split word count — close enough for OpenAI's
~0.75 tokens-per-word ratio and provider-independent.

Sprint 3 contract:
  * Idempotent — same input always yields the same chunk sequence.
  * Stable — chunk_index is preserved across re-runs.
  * Boundary-aware — prefers paragraph and sentence breaks over arbitrary
    word splits so semantic units stay together.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List


_PARA_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    token_count: int


def _approx_tokens(text: str) -> int:
    if not text:
        return 0
    # Words plus punctuation as a coarse approximation.
    return max(1, len(text.split()))


def _split_paragraphs(text: str) -> List[str]:
    parts = _PARA_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_sentences(paragraph: str) -> List[str]:
    parts = _SENTENCE_SPLIT.split(paragraph)
    return [s.strip() for s in parts if s.strip()]


def chunk_text(
    text: str,
    *,
    target_tokens: int = 220,
    overlap_tokens: int = 30,
    max_tokens: int = 320,
) -> List[Chunk]:
    """Greedy boundary-aware chunker.

    Goes paragraph → sentence → word, accumulating until ~target_tokens.
    Adds a tail of `overlap_tokens` from the previous chunk to the next so
    retrieval can match across chunk boundaries. Hard cap at max_tokens to
    bound LLM context budget per chunk.
    """
    if not text or not text.strip():
        return []

    paragraphs = _split_paragraphs(text)
    units: List[str] = []
    for p in paragraphs:
        if _approx_tokens(p) <= max_tokens:
            units.append(p)
        else:
            units.extend(_split_sentences(p))

    chunks: List[Chunk] = []
    buf: List[str] = []
    buf_tokens = 0
    last_tail: str = ""

    def flush():
        nonlocal buf, buf_tokens, last_tail
        if not buf:
            return
        body = " ".join(buf).strip()
        prefix = f"{last_tail} " if last_tail else ""
        full = (prefix + body).strip()
        chunks.append(
            Chunk(index=len(chunks), text=full, token_count=_approx_tokens(full))
        )
        # Tail = last `overlap_tokens` words for the next chunk's prefix.
        words = body.split()
        last_tail = " ".join(words[-overlap_tokens:]) if overlap_tokens > 0 else ""
        buf = []
        buf_tokens = 0

    for unit in units:
        unit_tokens = _approx_tokens(unit)
        if buf_tokens + unit_tokens > target_tokens and buf:
            flush()
        if unit_tokens > max_tokens:
            # Hard split very long sentences word-by-word.
            words = unit.split()
            sub: list[str] = []
            sub_tokens = 0
            for w in words:
                if sub_tokens + 1 > max_tokens and sub:
                    buf.append(" ".join(sub))
                    buf_tokens += sub_tokens
                    flush()
                    sub = []
                    sub_tokens = 0
                sub.append(w)
                sub_tokens += 1
            if sub:
                buf.append(" ".join(sub))
                buf_tokens += sub_tokens
            continue
        buf.append(unit)
        buf_tokens += unit_tokens
        if buf_tokens >= target_tokens:
            flush()

    if buf:
        flush()

    return chunks
