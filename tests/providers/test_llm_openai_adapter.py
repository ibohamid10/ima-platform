"""Unit tests for the OpenAI adapter."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
import respx
from pydantic import BaseModel

from ima.providers.llm.base import LLMMessage
from ima.providers.llm.exceptions import LLMProviderUnavailableError
from ima.providers.llm.openai_adapter import OpenAIAdapter


class DemoSchema(BaseModel):
    """Simple schema used for structured output tests."""

    label: str


def test_openai_supports_model() -> None:
    """Known OpenAI models should be reported as supported."""

    adapter = OpenAIAdapter(api_key="test-key")
    assert adapter.supports_model("gpt-5.4")
    assert adapter.supports_model("gpt-5.4-mini")
    assert adapter.supports_model("gpt-5.4-nano")
    assert not adapter.supports_model("claude-haiku-4-5-20251001")


@pytest.mark.asyncio()
@respx.mock
async def test_openai_complete_responses_api() -> None:
    """The adapter should normalize a Responses API payload."""

    respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "output": [{"content": [{"text": "hello from responses"}]}],
                "usage": {"input_tokens": 200, "output_tokens": 60},
            },
        )
    )
    adapter = OpenAIAdapter(api_key="test-key")
    response = await adapter.complete(
        messages=[LLMMessage(role="user", content="Say hello")],
        model="gpt-5.4-nano",
    )
    assert response.content == "hello from responses"
    assert response.cost_usd == Decimal("0.000044")


@pytest.mark.asyncio()
@respx.mock
async def test_openai_complete_structured_output() -> None:
    """Structured responses should pass through as JSON text."""

    respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "output": [{"content": [{"text": '{"label":"tech"}'}]}],
                "usage": {"input_tokens": 80, "output_tokens": 20},
            },
        )
    )
    adapter = OpenAIAdapter(api_key="test-key")
    response = await adapter.complete(
        messages=[LLMMessage(role="user", content="Classify")],
        model="gpt-5.4-nano",
        response_schema=DemoSchema,
    )
    assert response.content == '{"label":"tech"}'


@pytest.mark.asyncio()
@respx.mock
async def test_openai_falls_back_to_chat_completions() -> None:
    """A 404 from Responses API should trigger the chat-completions fallback."""

    responses_route = respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(404, json={"error": {"message": "not found"}})
    )
    chat_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"label":"food"}'}}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 10},
            },
        )
    )
    adapter = OpenAIAdapter(api_key="test-key")
    response = await adapter.complete(
        messages=[LLMMessage(role="user", content="Fallback")],
        model="gpt-5.4-nano",
        response_schema=DemoSchema,
    )
    assert response.content == '{"label":"food"}'
    assert responses_route.call_count == 1
    assert chat_route.call_count == 1


@pytest.mark.asyncio()
@respx.mock
async def test_openai_uses_status_code_for_chat_fallback() -> None:
    """A structured 400 from Responses API should trigger the explicit fallback path."""

    responses_route = respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(400, json={"error": {"message": "responses unsupported"}})
    )
    chat_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"label":"fallback-400"}'}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        )
    )
    adapter = OpenAIAdapter(api_key="test-key")
    response = await adapter.complete(
        messages=[LLMMessage(role="user", content="Fallback on 400")],
        model="gpt-5.4-nano",
        response_schema=DemoSchema,
    )

    assert response.content == '{"label":"fallback-400"}'
    assert responses_route.call_count == 1
    assert chat_route.call_count == 1


@pytest.mark.asyncio()
@respx.mock
async def test_openai_does_not_fallback_on_server_errors() -> None:
    """A 500 from Responses API should raise directly instead of silently falling back."""

    responses_route = respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(500, json={"error": {"message": "server boom"}})
    )
    chat_route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"label":"should-not-run"}'}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        )
    )
    adapter = OpenAIAdapter(api_key="test-key")

    with pytest.raises(LLMProviderUnavailableError) as exc_info:
        await adapter.complete(
            messages=[LLMMessage(role="user", content="Do not fallback")],
            model="gpt-5.4-nano",
            response_schema=DemoSchema,
        )

    assert exc_info.value.status_code == 500
    assert responses_route.call_count == 1
    assert chat_route.call_count == 0


@pytest.mark.asyncio()
@respx.mock
async def test_openai_rate_limit_raises() -> None:
    """A 429 from OpenAI should raise the dedicated rate-limit exception."""

    from ima.providers.llm.exceptions import LLMRateLimitError

    respx.post("https://api.openai.com/v1/responses").mock(
        return_value=httpx.Response(429, json={"error": {"message": "slow down"}})
    )
    adapter = OpenAIAdapter(api_key="test-key")
    with pytest.raises(LLMRateLimitError):
        await adapter.complete(
            messages=[LLMMessage(role="user", content="Rate limit")],
            model="gpt-5.4-nano",
        )


def test_openai_cost_formula() -> None:
    """Cost estimation should respect the configured price matrix."""

    adapter = OpenAIAdapter(api_key="test-key")
    cost = adapter.estimate_cost(1000, 500, "gpt-5.4")
    assert cost == Decimal("0.007500")
