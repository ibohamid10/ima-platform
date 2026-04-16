"""Base contracts for pluggable mail providers."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class OutboundMessage(BaseModel):
    """Normalized outbound email payload."""

    model_config = ConfigDict(extra="forbid")

    from_mailbox: str
    to: str
    subject: str
    body_plain: str
    body_html: str | None = None
    reply_to: str | None = None
    custom_headers: dict[str, str] = Field(default_factory=dict)


class SendResult(BaseModel):
    """Send result returned by a mail provider."""

    message_id: str
    provider: str
    sent_at: datetime


class InboundMessage(BaseModel):
    """Normalized inbound reply payload."""

    message_id: str
    in_reply_to: str | None
    from_address: str
    to_address: str
    subject: str
    body_plain: str
    received_at: datetime


class MailboxHealth(BaseModel):
    """Mailbox health summary used by sending guardrails."""

    mailbox: str
    sent_today: int
    bounce_rate_7d: float
    spam_complaint_rate_7d: float
    warmup_status: Literal["warming", "active", "paused"]


class MailProvider(Protocol):
    """Protocol implemented by all sending providers."""

    provider_name: str

    async def send(self, message: OutboundMessage) -> SendResult:
        """Send an outbound email."""

    async def fetch_replies(
        self, since: datetime, mailbox: str | None = None
    ) -> list[InboundMessage]:
        """Fetch inbound replies after a timestamp."""

    async def get_mailbox_health(self, mailbox: str) -> MailboxHealth:
        """Return mailbox health metrics."""

    async def list_mailboxes(self) -> list[str]:
        """List managed sender mailboxes."""
