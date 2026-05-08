"""LLM provider factory.

Selection (env): LLM_PROVIDER=local|anthropic (default: local).
Local provider produces deterministic templated synthesis from retrieved
context — no external dependencies. Anthropic provider lazy-imports the SDK
and requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import os
from functools import lru_cache

from .base import LLMProvider
from .local import LocalDeterministicLLM


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    name = (os.environ.get("LLM_PROVIDER") or "local").lower()
    if name == "anthropic":
        try:
            from .anthropic_provider import AnthropicLLM

            return AnthropicLLM()
        except Exception:
            import logging

            logging.getLogger(__name__).warning(
                "anthropic LLM provider unavailable; falling back to local"
            )
            return LocalDeterministicLLM()
    return LocalDeterministicLLM()


__all__ = ["LLMProvider", "get_provider"]
