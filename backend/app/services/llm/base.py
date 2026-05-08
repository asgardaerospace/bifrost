"""LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    confidence: float  # 0..1
    model: str
    raw: dict


class LLMProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def synthesize(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
    ) -> LLMResponse:  # pragma: no cover
        ...
