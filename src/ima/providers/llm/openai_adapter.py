"""OpenAI adapter implementation behind the LLMProvider boundary."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel

from ima.config import settings
from ima.providers.llm.base import LLMMessage, LLMProvider, LLMResponse
from ima.providers.llm.exceptions import (
    LLMInvalidResponseError,
    LLMProviderUnavailableError,
    LLMRateLimitError,
)


class OpenAIAdapter(LLMProvider):
    """OpenAI Responses API adapter with chat fallback."""

    provider_name = "openai"

    MODEL_PRICES: dict[str, tuple[Decimal, Decimal]] = {
        "gpt-5.4": (Decimal("2.50"), Decimal("10.00")),  # TODO: Preise vor Production verifizieren
        "gpt-5.4-mini": (
            Decimal("0.40"),
            Decimal("1.60"),
        ),  # TODO: Preise vor Production verifizieren
        "gpt-5.4-nano": (
            Decimal("0.10"),
            Decimal("0.40"),
        ),  # TODO: Preise vor Production verifizieren
    }

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
    ) -> None:
        """Create a new OpenAI adapter."""

        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def supports_model(self, model: str) -> bool:
        """Return whether the model is supported by OpenAI."""

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
        """Call OpenAI Responses API with chat fallback."""

        if not self.api_key:
            raise LLMProviderUnavailableError("OPENAI_API_KEY ist nicht gesetzt.")
        if not self.supports_model(model):
            raise LLMProviderUnavailableError(f"OpenAI unterstuetzt Modell {model} nicht.")

        try:
            raw_response = await self._post_responses(
                messages, model, response_schema, temperature, max_tokens
            )
            return self._normalize_responses_api(raw_response, model)
        except LLMProviderUnavailableError as exc:
            if exc.status_code not in {400, 404}:
                raise
            raw_response = await self._post_chat_completions(
                messages, model, response_schema, temperature, max_tokens
            )
            return self._normalize_chat_completions(raw_response, model)

    async def _post_responses(
        self,
        messages: list[LLMMessage],
        model: str,
        response_schema: type[BaseModel] | None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Call the Responses API."""

        payload: dict[str, Any] = {
            "model": model,
            "input": [
                {
                    "role": message.role,
                    "content": [{"type": "input_text", "text": message.content}],
                }
                for message in messages
            ],
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if response_schema is not None:
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": "structured_output",
                    "schema": response_schema.model_json_schema(),
                }
            }
        return await self._post("/responses", payload)

    async def _post_chat_completions(
        self,
        messages: list[LLMMessage],
        model: str,
        response_schema: type[BaseModel] | None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Call the Chat Completions API as a fallback."""

        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.model_dump() for message in messages],
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": response_schema.model_json_schema(),
                },
            }
        return await self._post("/chat/completions", payload)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST to the OpenAI API and normalize transport errors."""

        headers = {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.post(path, headers=headers, json=payload)

        if response.status_code == 429:
            raise LLMRateLimitError("OpenAI rate limit reached.")
        if response.status_code >= 400:
            raise LLMProviderUnavailableError(
                f"OpenAI request failed: {response.status_code} {response.text}",
                status_code=response.status_code,
            )
        return response.json()

    def _normalize_responses_api(self, raw_response: dict[str, Any], model: str) -> LLMResponse:
        """Normalize a Responses API payload."""

        output_items = raw_response.get("output", [])
        text_chunks: list[str] = []
        for item in output_items:
            for content_block in item.get("content", []):
                if "text" in content_block:
                    text_chunks.append(str(content_block["text"]))

        content = "\n".join(text_chunks).strip() or raw_response.get("output_text", "")
        if not content:
            raise LLMInvalidResponseError("OpenAI Responses API lieferte keinen Text zurueck.")

        usage = raw_response.get("usage", {})
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

    def _normalize_chat_completions(self, raw_response: dict[str, Any], model: str) -> LLMResponse:
        """Normalize a Chat Completions payload."""

        try:
            message = raw_response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMInvalidResponseError(
                "OpenAI Chat Completions Antwort war unvollstaendig."
            ) from exc

        content = message if isinstance(message, str) else json.dumps(message)
        usage = raw_response.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self.estimate_cost(input_tokens, output_tokens, model),
            raw_response=raw_response,
        )
