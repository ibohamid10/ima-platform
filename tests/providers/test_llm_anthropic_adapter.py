"""Unit tests for the Anthropic adapter."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
import respx
from pydantic import BaseModel

from ima.providers.llm.anthropic_adapter import AnthropicAdapter
from ima.providers.llm.base import LLMMessage


class DemoSchema(BaseModel):
    """Simple schema used for structured output tests."""

    label: str


def test_anthropic_supports_model() -> None:
    """Known Anthropic models should be reported as supported."""

    adapter = AnthropicAdapter(api_key="test-key")
    assert adapter.supports_model("claude-opus-4-6")
    assert adapter.supports_model("claude-sonnet-4-6")
    assert adapter.supports_model("claude-haiku-4-5-20251001")
    assert not adapter.supports_model("gpt-5.4")


@pytest.mark.asyncio()
@respx.mock
async def test_anthropic_complete_simple_prompt() -> None:
    """The adapter should normalize a plain text Anthropic response."""

    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "hello world"}],
                "usage": {"input_tokens": 120, "output_tokens": 40},
            },
        )
    )
    adapter = AnthropicAdapter(api_key="test-key")
    response = await adapter.complete(
        messages=[LLMMessage(role="user", content="Say hello")],
        model="claude-haiku-4-5-20251001",
    )
    assert response.content == "hello world"
    assert response.cost_usd == Decimal("0.000320")


@pytest.mark.asyncio()
@respx.mock
async def test_anthropic_complete_structured_output() -> None:
    """Structured output should be returned as serialized JSON."""

    respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [
                    {"type": "tool_use", "name": "structured_output", "input": {"label": "fitness"}}
                ],
                "usage": {"input_tokens": 50, "output_tokens": 20},
            },
        )
    )
    adapter = AnthropicAdapter(api_key="test-key")
    response = await adapter.complete(
        messages=[LLMMessage(role="user", content="Classify")],
        model="claude-haiku-4-5-20251001",
        response_schema=DemoSchema,
    )
    assert response.content == '{"label": "fitness"}'


@pytest.mark.asyncio()
@respx.mock
async def test_anthropic_rate_limit_retry() -> None:
    """A 429 response should trigger a retry that can eventually succeed."""

    route = respx.post("https://api.anthropic.com/v1/messages")
    route.side_effect = [
        httpx.Response(429, json={"error": {"message": "rate limit"}}),
        httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "retry success"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        ),
    ]
    adapter = AnthropicAdapter(api_key="test-key")
    response = await adapter.complete(
        messages=[LLMMessage(role="user", content="Retry")],
        model="claude-haiku-4-5-20251001",
    )
    assert response.content == "retry success"
    assert route.call_count == 2


def test_anthropic_cost_formula() -> None:
    """Cost estimation should respect the configured price matrix."""

    adapter = AnthropicAdapter(api_key="test-key")
    cost = adapter.estimate_cost(1000, 500, "claude-sonnet-4-6")
    assert cost == Decimal("0.010500")
