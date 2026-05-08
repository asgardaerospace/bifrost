"""Deterministic local LLM — synthesizes from prompt + retrieval block.

Emits a stable, structured summary anchored to whatever context appears in
the user_prompt. Used by tests, by demos that have no API key, and as a
permanent fallback when Anthropic is unavailable.

The synthesis explicitly cites chunks by `[#k]` style markers found in the
prompt — matches the RAG layer's citation extractor.
"""

from __future__ import annotations

import re

from .base import LLMProvider, LLMResponse


_CITATION_RE = re.compile(r"\[#(\d+)\]")
_RETRIEVAL_BLOCK_RE = re.compile(
    r"<retrieved>\s*(.*?)\s*</retrieved>", re.DOTALL
)
_TASK_TAG_RE = re.compile(r"<task>\s*(.*?)\s*</task>", re.DOTALL)


def _shorten(text: str, max_words: int = 28) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


class LocalDeterministicLLM(LLMProvider):
    name = "local-deterministic-v1"

    def synthesize(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
    ) -> LLMResponse:
        retrieval_match = _RETRIEVAL_BLOCK_RE.search(user_prompt)
        task_match = _TASK_TAG_RE.search(user_prompt)

        body = retrieval_match.group(1) if retrieval_match else ""
        task = task_match.group(1).strip() if task_match else "Synthesize"

        # Pull every cited chunk and produce one anchored bullet per chunk.
        bullets: list[str] = []
        for line in body.splitlines():
            m = _CITATION_RE.search(line)
            if m:
                ref = m.group(0)
                stripped = _CITATION_RE.sub("", line).strip()
                if stripped:
                    bullets.append(f"- {_shorten(stripped)} {ref}")

        if not bullets:
            text = (
                f"{task}: insufficient retrieved context to synthesize a "
                "grounded answer. The retrieval pipeline returned no chunks "
                "above the relevance threshold."
            )
            confidence = 0.0
        else:
            head = f"{task} — synthesized from {len(bullets)} retrieved record(s):"
            text = head + "\n\n" + "\n".join(bullets[:8])
            # Higher confidence when more chunks support the synthesis. Cap at
            # 0.9 — we never claim certainty in deterministic mode.
            confidence = min(0.9, 0.4 + 0.08 * len(bullets))

        return LLMResponse(
            text=text,
            confidence=confidence,
            model=self.name,
            raw={"bullets": len(bullets)},
        )
