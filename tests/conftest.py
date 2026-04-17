"""Shared fixtures and test doubles for the IMA platform."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ima.db.models import Base
from ima.providers.llm.base import LLMMessage, LLMResponse
from ima.providers.llm.exceptions import LLMProviderUnavailableError


@dataclass
class FakeTrace:
    """Simple trace handle used in tests."""

    trace_id: str | None = "trace-test"
    trace_url: str | None = "http://localhost:3000/project/default/traces/trace-test"

    def finish(self, **_: Any) -> None:
        """No-op finish implementation."""


@dataclass
class FakeGeneration:
    """Simple generation handle used in tests."""

    trace_id: str | None = "trace-test"

    def update(self, **_: Any) -> None:
        """No-op update implementation."""

    def finish(self) -> None:
        """No-op finish implementation."""


class FakeLangfuseHook:
    """No-op Langfuse hook used in tests."""

    def start_trace(
        self, name: str, input_payload: dict[str, Any], metadata: dict[str, Any]
    ) -> FakeTrace:
        """Return a fake trace handle."""

        _ = (name, input_payload, metadata)
        return FakeTrace()

    def start_generation(
        self, name: str, model: str, provider: str, input_payload: list[dict[str, str]]
    ) -> FakeGeneration:
        """Return a fake generation handle."""

        _ = (name, model, provider, input_payload)
        return FakeGeneration()

    def flush(self) -> None:
        """No-op flush implementation."""


class FakeLLMProvider:
    """Programmable provider double for executor and golden-set tests."""

    def __init__(
        self,
        provider_name: str,
        supported_models: set[str],
        responses: list[str] | None = None,
        unavailable: bool = False,
    ) -> None:
        """Create a fake provider with predetermined behavior."""

        self.provider_name = provider_name
        self.supported_models = supported_models
        self.responses = responses or []
        self.unavailable = unavailable
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Return the next queued response or raise unavailability."""

        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "response_schema": response_schema,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.unavailable:
            raise LLMProviderUnavailableError(f"{self.provider_name} unavailable")
        content = self.responses.pop(0)
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.001"),
            raw_response={"content": content},
        )

    def supports_model(self, model: str) -> bool:
        """Return whether the fake provider accepts the model."""

        return model in self.supported_models

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> Decimal:
        """Return a predictable fake cost."""

        _ = (input_tokens, output_tokens, model)
        return Decimal("0.001")


class RuleBasedClassifierProvider(FakeLLMProvider):
    """Deterministic provider for classifier golden-set tests."""

    def __init__(self, provider_name: str = "mock") -> None:
        """Create the deterministic provider."""

        super().__init__(
            provider_name=provider_name,
            supported_models={"claude-haiku-4-5-20251001", "gpt-5.4-nano"},
        )

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a deterministic classifier result from the user payload."""

        _ = (response_schema, temperature, max_tokens)
        payload = json.loads(messages[-1].content)
        handle = payload["creator_handle"]
        mapping = load_classifier_cases()
        expected = mapping[handle]["expected"]
        content = json.dumps(
            {
                "niche": expected["niche"],
                "sub_niches": expected.get("sub_niches", []),
                "language": expected["language"],
                "brand_safety_score": expected["brand_safety_score_min"],
                "reasoning": "Deterministic golden-set mock response.",
            }
        )
        self.calls.append({"messages": messages, "model": model})
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=100,
            output_tokens=40,
            cost_usd=Decimal("0.0005"),
            raw_response={"content": content},
        )


class RuleBasedEvidenceBuilderProvider(FakeLLMProvider):
    """Deterministic provider for evidence-builder golden-set tests."""

    def __init__(self, provider_name: str = "mock") -> None:
        """Create the deterministic provider."""

        super().__init__(
            provider_name=provider_name,
            supported_models={"claude-sonnet-4-6", "gpt-5.4"},
        )

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate deterministic evidence items from the golden-set case mapping."""

        _ = (response_schema, temperature, max_tokens)
        payload = json.loads(messages[-1].content)
        case = load_evidence_builder_cases()[payload["creator_handle"]]
        expected = case["expected"]
        recent_content = payload.get("recent_content", [])
        default_source_uri = "evidence://missing-source"
        default_source_type = "bio" if not recent_content else recent_content[0]["source_type"]

        items: list[dict[str, object]] = []
        if payload.get("bio"):
            items.append(
                {
                    "claim_text": payload["bio"],
                    "source_uri": "bio" if not recent_content else default_source_uri,
                    "source_type": "bio",
                    "confidence": max(expected["min_confidence"], 0.5),
                }
            )

        for record in recent_content:
            items.append(
                {
                    "claim_text": record.get("title")
                    or record.get("caption")
                    or "Recent content observed.",
                    "source_uri": record["source_uri"],
                    "source_type": record["source_type"],
                    "confidence": max(
                        expected["min_confidence"],
                        record.get("sponsor_probability") or 0.55,
                    ),
                }
            )

        while len(items) < expected["min_items"]:
            items.append(
                {
                    "claim_text": f"Metric snapshot for {payload['creator_handle']}.",
                    "source_uri": payload["metrics"].get("metrics_source_uri", default_source_uri),
                    "source_type": default_source_type,
                    "confidence": expected["min_confidence"],
                }
            )

        content = json.dumps({"evidence_items": items})
        self.calls.append({"messages": messages, "model": model})
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=140,
            output_tokens=120,
            cost_usd=Decimal("0.0010"),
            raw_response={"content": content},
        )


def load_classifier_cases() -> dict[str, dict[str, Any]]:
    """Load classifier golden-set cases keyed by creator handle."""

    cases_path = Path("tests/golden_sets/classifier/cases.yaml")
    cases = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    return {case["input"]["creator_handle"]: case for case in cases}


def load_evidence_builder_cases() -> dict[str, dict[str, Any]]:
    """Load evidence-builder golden-set cases keyed by creator handle."""

    cases_path = Path("tests/golden_sets/evidence_builder/cases.yaml")
    cases = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    return {case["input"]["creator_handle"]: case for case in cases}


@pytest.fixture()
async def sqlite_session_factory(tmp_path: Path) -> async_sessionmaker[AsyncSession]:
    """Create an isolated async SQLite session factory for tests."""

    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture()
def fake_langfuse_hook() -> FakeLangfuseHook:
    """Return a fake Langfuse hook."""

    return FakeLangfuseHook()
