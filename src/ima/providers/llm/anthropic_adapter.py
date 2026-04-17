"""Anthropic adapter implementation behind the LLMProvider boundary."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ima.config import settings
from ima.logging import get_logger
from ima.providers.llm.base import LLMMessage, LLMProvider, LLMResponse
from ima.providers.llm.exceptions import (
    LLMInvalidResponseError,
    LLMProviderUnavailableError,
    LLMRateLimitError,
)

logger = get_logger(__name__)


class AnthropicAdapter(LLMProvider):
    """Anthropic Messages API adapter with optional structured output."""

    provider_name = "anthropic"

    MODEL_PRICES: dict[str, tuple[Decimal, Decimal]] = {
        "claude-opus-4-6": (Decimal("5.00"), Decimal("25.00")),
        "claude-sonnet-4-6": (Decimal("3.00"), Decimal("15.00")),
        "claude-haiku-4-5-20251001": (Decimal("1.00"), Decimal("5.00")),
    }

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = 30.0,
    ) -> None:
        """Create a new Anthropic adapter."""

        self.api_key = api_key or settings.anthropic_api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def supports_model(self, model: str) -> bool:
        """Return whether the model is supported by Anthropic."""

        return model in self.MODEL_PRICES

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> Decimal:
        """Estimate request cost from the configured price matrix."""

        input_rate, output_rate = self.MODEL_PRICES[model]
        return ((input_rate * input_tokens) + (output_rate * output_tokens)) / Decimal("1000000")

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Call Anthropic and normalize the response."""

        if not self.api_key:
            raise LLMProviderUnavailableError("ANTHROPIC_API_KEY ist nicht gesetzt.")
        if not self.supports_model(model):
            raise LLMProviderUnavailableError(f"Anthropic unterstuetzt Modell {model} nicht.")

        payload = self._build_payload(messages, model, response_schema, temperature, max_tokens)
        raw_response = await self._post_messages(payload)
        return self._normalize_response(raw_response, model, response_schema)

    def _build_payload(
        self,
        messages: list[LLMMessage],
        model: str,
        response_schema: type[BaseModel] | None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Build the Anthropic request payload."""

        system_messages = [message.content for message in messages if message.role == "system"]
        user_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role != "system"
        ]
        payload: dict[str, Any] = {
            "model": model,
            "system": "\n\n".join(system_messages),
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_schema is not None:
            payload["tools"] = [
                {
                    "name": "structured_output",
                    "description": "Return the final answer as structured JSON input.",
                    "input_schema": response_schema.model_json_schema(),
                }
            ]
            payload["tool_choice"] = {"type": "tool", "name": "structured_output"}
        return payload

    @retry(
        retry=retry_if_exception_type(LLMRateLimitError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _post_messages(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a Messages API request with rate-limit retry."""

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.post("/messages", headers=headers, json=payload)

        if response.status_code == 429:
            logger.warning("anthropic_rate_limited")
            raise LLMRateLimitError("Anthropic rate limit reached.")
        if response.status_code >= 500:
            raise LLMProviderUnavailableError(
                f"Anthropic server error: {response.status_code} {response.text}"
            )
        if response.status_code >= 400:
            raise LLMProviderUnavailableError(
                f"Anthropic request failed: {response.status_code} {response.text}"
            )
        return response.json()

    def _normalize_response(
        self,
        raw_response: dict[str, Any],
        model: str,
        response_schema: type[BaseModel] | None,
    ) -> LLMResponse:
        """Normalize an Anthropic response to LLMResponse."""

        usage = raw_response.get("usage", {})
        content_blocks = raw_response.get("content", [])
        if response_schema is not None:
            tool_block = next(
                (block for block in content_blocks if block.get("type") == "tool_use"),
                None,
            )
            if tool_block is None or "input" not in tool_block:
                raise LLMInvalidResponseError("Anthropic lieferte keinen tool_use-Block zurueck.")
            content = json.dumps(tool_block["input"])
        else:
            text_chunks = [
                block.get("text", "") for block in content_blocks if block.get("type") == "text"
            ]
            content = "\n".join(chunk for chunk in text_chunks if chunk).strip()
            if not content:
                raise LLMInvalidResponseError("Anthropic lieferte keinen Textinhalt zurueck.")

        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self.estimate_cost(input_tokens, output_tokens, model),
            raw_response=raw_response,
        )
