"""Transport layer to the investor engine.

Kept deliberately thin — just enough to fetch a raw payload and hand
it to the schemas for validation. Swap the implementation (HTTP,
local file, gRPC, queue consumer) without touching the mapper or sync.

Mutation surface: the writer service calls `apply_mutation` to push
changes back to the engine. The default file-backed client treats
mutations as a recorded no-op so local development stays deterministic
— production clients wire this up to the real engine API.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

from app.integrations.investor_engine.schemas import EnginePayload


class EngineMutationResult:
    """Outcome of a mutation call."""

    def __init__(
        self,
        *,
        success: bool,
        engine_updated_at: Optional[datetime] = None,
        error: Optional[str] = None,
        response: Optional[dict[str, Any]] = None,
    ) -> None:
        self.success = success
        self.engine_updated_at = engine_updated_at
        self.error = error
        self.response = response or {}


class InvestorEngineClient(Protocol):
    def fetch_payload(self) -> EnginePayload: ...

    def apply_mutation(
        self,
        *,
        external_id: str,
        action_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> EngineMutationResult: ...


class FileInvestorEngineClient:
    """Reads the engine payload from a local JSON file.

    Useful for bring-up and tests. Real deployments inject an
    HTTP-backed implementation that satisfies the Protocol above.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._mutation_log: list[dict[str, Any]] = []

    def fetch_payload(self) -> EnginePayload:
        with self._path.open("r", encoding="utf-8") as fh:
            raw: Any = json.load(fh)
        return EnginePayload.model_validate(raw)

    def apply_mutation(
        self,
        *,
        external_id: str,
        action_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> EngineMutationResult:
        # Local dev: record the mutation and pretend the engine accepted it.
        now = datetime.now(timezone.utc)
        self._mutation_log.append(
            {
                "external_id": external_id,
                "action_type": action_type,
                "payload": payload,
                "idempotency_key": idempotency_key,
                "applied_at": now.isoformat(),
            }
        )
        return EngineMutationResult(
            success=True,
            engine_updated_at=now,
            response={"applied": True, "mode": "local_stub"},
        )

    @property
    def mutation_log(self) -> list[dict[str, Any]]:
        return list(self._mutation_log)


class StaticInvestorEngineClient:
    """In-memory client, primarily for tests and fixtures."""

    def __init__(self, payload: EnginePayload | dict[str, Any]) -> None:
        self._payload = (
            payload
            if isinstance(payload, EnginePayload)
            else EnginePayload.model_validate(payload)
        )
        self.mutation_log: list[dict[str, Any]] = []
        self.next_failure: Optional[str] = None

    def fetch_payload(self) -> EnginePayload:
        return self._payload

    def apply_mutation(
        self,
        *,
        external_id: str,
        action_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> EngineMutationResult:
        if self.next_failure is not None:
            err = self.next_failure
            self.next_failure = None
            return EngineMutationResult(success=False, error=err)
        now = datetime.now(timezone.utc)
        self.mutation_log.append(
            {
                "external_id": external_id,
                "action_type": action_type,
                "payload": payload,
                "idempotency_key": idempotency_key,
            }
        )
        return EngineMutationResult(success=True, engine_updated_at=now)


_default_client: Optional[InvestorEngineClient] = None


def set_default_client(client: InvestorEngineClient) -> None:
    """Wire up the process-wide client (called at app startup)."""
    global _default_client
    _default_client = client


def get_default_client() -> InvestorEngineClient:
    if _default_client is None:
        raise RuntimeError(
            "Investor engine client is not configured. "
            "Call set_default_client() at startup."
        )
    return _default_client
