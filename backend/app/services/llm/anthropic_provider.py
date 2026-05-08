"""Anthropic LLM provider — Claude Haiku for grounded synthesis.

Lazy-imports the anthropic SDK. Reads ANTHROPIC_API_KEY from env. Defaults
to claude-haiku-4-5 for low-latency synthesis; can be overridden via
ANTHROPIC_MODEL env.
"""

from __future__ import annotations

import os

from .base import LLMProvider, LLMResponse


class AnthropicLLM(LLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set; cannot use Anthropic LLM provider"
            )
        try:
            from anthropic import Anthropic  # type: ignore
        except ImportError as e:
            raise ImportError(
                "anthropic package not installed; pip install anthropic"
            ) from e
        self._client = Anthropic(api_key=api_key)
        self._model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

    def synthesize(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
    ) -> LLMResponse:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        return LLMResponse(
            text=text,
            confidence=0.85,  # Anthropic doesn't return logprobs; flat estimate.
            model=resp.model,
            raw={
                "input_tokens": getattr(resp.usage, "input_tokens", None),
                "output_tokens": getattr(resp.usage, "output_tokens", None),
                "stop_reason": resp.stop_reason,
            },
        )
