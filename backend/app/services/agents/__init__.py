"""Agent registry — finite, code-defined, inspectable.

Doctrine: agents are program code. Their metadata is colocated with their
implementation; runtime configuration lives in the database (autonomy
operations + workflow stages) rather than in the agent definition itself.

This module exposes:
  * REGISTRY        — name → BaseAgent instance
  * register(agent) — explicit registration
  * get(name)       — typed lookup
  * descriptors()   — read-side metadata for the /agents API

No agent is loaded by side effect — every canonical agent is imported here
and registered. Sprint 6 ships with 6 canonical agents.
"""

from __future__ import annotations

from typing import Iterable, Optional

from .base import AgentDescriptor, BaseAgent


REGISTRY: dict[str, BaseAgent] = {}


def register(agent: BaseAgent) -> BaseAgent:
    if agent.name in REGISTRY:
        raise ValueError(f"agent '{agent.name}' already registered")
    REGISTRY[agent.name] = agent
    return agent


def get(name: str) -> Optional[BaseAgent]:
    return REGISTRY.get(name)


def descriptors() -> list[AgentDescriptor]:
    return [a.descriptor() for a in REGISTRY.values()]


def all_agents() -> Iterable[BaseAgent]:
    return REGISTRY.values()


# Canonical agent imports — import-time side effect: each module calls
# `register(...)` on its singleton. Order is irrelevant.
from . import (  # noqa: F401, E402
    capital_monitoring_agent,
    executive_briefing_agent,
    intelligence_agent,
    mission_coordination_agent,
    queue_coordination_agent,
    supplier_risk_agent,
)


__all__ = [
    "AgentDescriptor",
    "BaseAgent",
    "REGISTRY",
    "register",
    "get",
    "descriptors",
    "all_agents",
]
