"""Unit tests for the Instantly adapter."""

from __future__ import annotations

import httpx
import pytest
import respx

from ima.providers.mail.base import OutboundMessage
from ima.providers.mail.instantly_adapter import InstantlyAdapter


@pytest.mark.asyncio()
async def test_instantly_send_requires_api_key() -> None:
    """Without an API key the adapter should refuse live sends."""

    adapter = InstantlyAdapter(api_key=None)
    with pytest.raises(NotImplementedError):
        await adapter.send(
            OutboundMessage(
                from_mailbox="ops@example.com",
                to="brand@example.com",
                subject="Hello",
                body_plain="Test",
            )
        )


@pytest.mark.asyncio()
@respx.mock
async def test_instantly_send_success() -> None:
    """A successful API response should be normalized into SendResult."""

    respx.post("https://api.instantly.ai/api/v2/emails/test").mock(
        return_value=httpx.Response(200, json={"message_id": "msg-123"})
    )
    adapter = InstantlyAdapter(api_key="test-key")
    result = await adapter.send(
        OutboundMessage(
            from_mailbox="ops@example.com",
            to="brand@example.com",
            subject="Hello",
            body_plain="Test body",
        )
    )
    assert result.message_id == "msg-123"
    assert result.provider == "instantly"


@pytest.mark.asyncio()
@respx.mock
async def test_instantly_mailbox_health() -> None:
    """Mailbox health should be mapped from the API response."""

    respx.get("https://api.instantly.ai/api/v2/accounts").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "email": "ops@example.com",
                        "status": "active",
                        "emails_sent_today": 12,
                        "bounce_rate_7d": 0.01,
                        "spam_complaint_rate_7d": 0.0,
                    }
                ]
            },
        )
    )
    adapter = InstantlyAdapter(api_key="test-key")
    health = await adapter.get_mailbox_health("ops@example.com")
    assert health.mailbox == "ops@example.com"
    assert health.sent_today == 12
    assert health.warmup_status == "active"
