"""Instantly adapter implementation for the MailProvider protocol."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from ima.config import settings
from ima.providers.mail.base import (
    InboundMessage,
    MailboxHealth,
    MailProvider,
    OutboundMessage,
    SendResult,
)
from ima.providers.mail.exceptions import MailProviderUnavailableError, MailRateLimitError

# NOTE: Echte Integration wird in Woche 6 live.
# Adapter dient in Woche 1 primaer als Interface-Validation.


class InstantlyAdapter(MailProvider):
    """Thin Instantly adapter for week-1 interface validation."""

    provider_name = "instantly"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.instantly.ai/api/v2",
        timeout: float = 30.0,
    ) -> None:
        """Create a new Instantly adapter."""

        self.api_key = api_key or settings.instantly_api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def send(self, message: OutboundMessage) -> SendResult:
        """Send a test email through Instantly when credentials are configured."""

        if not self.api_key:
            raise NotImplementedError(
                "INSTANTLY_API_KEY ist nicht gesetzt. "
                "Die Live-Integration wird in Woche 6 aktiviert."
            )

        payload = {
            "from_address_email": message.from_mailbox,
            "to_address_email_list": message.to,
            "reply_to": message.reply_to,
            "subject": message.subject,
            "body": {"text": message.body_plain, "html": message.body_html},
            "headers": message.custom_headers,
        }
        raw_response = await self._request("POST", "/emails/test", payload)
        return SendResult(
            message_id=raw_response.get("message_id", raw_response.get("id", "unknown")),
            provider=self.provider_name,
            sent_at=datetime.now(UTC),
        )

    async def fetch_replies(
        self, since: datetime, mailbox: str | None = None
    ) -> list[InboundMessage]:
        """Fetch replies for a mailbox after the provided timestamp."""

        if not self.api_key:
            raise NotImplementedError(
                "Reply-Fetching wird in Woche 6 mit echter API-Doku aktiviert."
            )

        params: dict[str, Any] = {"timestamp_created_gt": since.isoformat()}
        if mailbox is not None:
            params["from_address_email"] = mailbox
        raw_response = await self._request("GET", "/emails", params=params)
        items = raw_response.get("items", [])
        return [
            InboundMessage(
                message_id=item["message_id"],
                in_reply_to=item.get("in_reply_to"),
                from_address=item.get("from_address_email", ""),
                to_address=item.get("to_address_email_list", ""),
                subject=item.get("subject", ""),
                body_plain=item.get("body", {}).get("text", ""),
                received_at=datetime.fromisoformat(item["timestamp_email"].replace("Z", "+00:00")),
            )
            for item in items
        ]

    async def get_mailbox_health(self, mailbox: str) -> MailboxHealth:
        """Return a simplified mailbox health record."""

        if not self.api_key:
            raise NotImplementedError(
                "Mailbox-Health wird in Woche 6 mit echter API-Doku aktiviert."
            )

        raw_response = await self._request("GET", "/accounts", params={"search": mailbox})
        first_item = raw_response.get("items", [{}])[0]
        warmup_status = "warming"
        if first_item.get("status") == "active":
            warmup_status = "active"
        if first_item.get("status") == "paused":
            warmup_status = "paused"

        return MailboxHealth(
            mailbox=mailbox,
            sent_today=int(first_item.get("emails_sent_today", 0)),
            bounce_rate_7d=float(first_item.get("bounce_rate_7d", 0.0)),
            spam_complaint_rate_7d=float(first_item.get("spam_complaint_rate_7d", 0.0)),
            warmup_status=warmup_status,
        )

    async def list_mailboxes(self) -> list[str]:
        """List known sending mailboxes from Instantly."""

        if not self.api_key:
            raise NotImplementedError(
                "Mailbox-Listing wird in Woche 6 mit echter API-Doku aktiviert."
            )

        raw_response = await self._request("GET", "/accounts")
        return [item["email"] for item in raw_response.get("items", []) if "email" in item]

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform an authenticated request against the Instantly API."""

        if not self.api_key:
            raise MailProviderUnavailableError("INSTANTLY_API_KEY ist nicht gesetzt.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.request(
                method, path, headers=headers, json=payload, params=params
            )

        if response.status_code == 429:
            raise MailRateLimitError("Instantly rate limit reached.")
        if response.status_code >= 400:
            raise MailProviderUnavailableError(
                f"Instantly request failed: {response.status_code} {response.text}"
            )
        return response.json()
