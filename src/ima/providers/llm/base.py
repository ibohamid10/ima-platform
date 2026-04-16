"""Base contracts for pluggable LLM providers."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict


class LLMMessage(BaseModel):
    """Normalized message format for provider adapters."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    """Normalized response payload returned by provider adapters."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    raw_response: dict[str, Any]


class LLMProvider(Protocol):
    """Protocol implemented by every LLM provider adapter."""

    provider_name: str

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Complete a prompt and return a normalized response."""

    def supports_model(self, model: str) -> bool:
        """Return whether the adapter supports the requested model."""

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> Decimal:
        """Estimate request cost for logging and budget tracking."""
