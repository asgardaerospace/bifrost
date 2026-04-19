"""Email send boundary.

All outbound email goes through an EmailProvider. Phase 1 ships a
StubEmailProvider that records intent without external delivery — we do not
wire a real SMTP/API client until an integration is explicitly approved.

No router should import this module directly; only service-layer code may
call ``send_communication``.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.models.communication import Communication

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    success: bool
    provider: str
    sent_at: datetime
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def send(self, communication: Communication) -> SendResult: ...


class StubEmailProvider(EmailProvider):
    """Records intent, performs no external delivery. Safe default."""

    name = "stub"

    def send(self, communication: Communication) -> SendResult:
        logger.info(
            "email.stub.send",
            extra={
                "communication_id": communication.id,
                "to": communication.to_address,
                "from": communication.from_address,
                "subject": communication.subject,
            },
        )
        return SendResult(
            success=True,
            provider=self.name,
            sent_at=datetime.now(timezone.utc),
            message_id=f"stub-{communication.id}",
        )


_provider: EmailProvider = StubEmailProvider()


def get_email_provider() -> EmailProvider:
    return _provider


def set_email_provider(provider: EmailProvider) -> None:
    """Allow wiring a real provider from app startup or tests."""
    global _provider
    _provider = provider


def send_communication(communication: Communication) -> SendResult:
    return get_email_provider().send(communication)
