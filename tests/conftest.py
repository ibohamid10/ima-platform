"""Shared fixtures and test doubles for the IMA platform."""

from __future__ import annotations

import json
import re
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


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    """Return whether the normalized text contains one of the given keywords."""

    return any(keyword in text for keyword in keywords)


def _detect_language(text: str) -> str:
    """Derive a dominant language from simple lexical signals."""

    german_markers = (
        " deutsch",
        " ernaehrung",
        " heute",
        " fuer ",
        " rezepte",
        " schnelle",
        " tagespolitik",
        " meinungen",
        " luegen",
        " wien",
        " berlin",
        " muenchen",
    )
    english_markers = (
        " english",
        " strength",
        " injury",
        " free",
        " cozy",
        " sunday",
        " cafes",
        " worth",
        " shipping",
        " workflows",
        " adult jokes",
        " routine",
    )
    german_score = sum(text.count(marker) for marker in german_markers)
    english_score = sum(text.count(marker) for marker in english_markers)
    return "de" if german_score >= english_score else "en"


def _derive_classifier_result(payload: dict[str, Any]) -> dict[str, object]:
    """Infer a deterministic classifier output from the input payload only."""

    raw_text = " ".join(
        [
            payload.get("bio", ""),
            *payload.get("recent_captions", []),
            *payload.get("top_hashtags", []),
        ]
    )
    normalized = re.sub(r"[^a-z0-9#& ]+", " ", raw_text.lower())

    if _contains_any(normalized, ("politik", "medien", "kontroverse", "meinung")):
        return {
            "niche": "other",
            "sub_niches": ["politics", "commentary"],
            "language": _detect_language(normalized),
            "brand_safety_score": 2,
            "reasoning": "Political or controversial commentary lowers brand safety.",
        }

    if _contains_any(normalized, ("adult", "explicit", "nsfw", "shock humor", "drama")):
        return {
            "niche": "other",
            "sub_niches": ["shock-humor", "drama"],
            "language": _detect_language(normalized),
            "brand_safety_score": 1,
            "reasoning": "Explicit or shock-oriented content is unsafe for most brands.",
        }

    niche_scores = {
        "fitness": sum(
            normalized.count(keyword)
            for keyword in (
                "hyrox",
                "fitness",
                "training",
                "runner",
                "running",
                "strength",
                "mobility",
                "workout",
                "coach",
                "athlete",
            )
        ),
        "food": sum(
            normalized.count(keyword)
            for keyword in (
                "rezepte",
                "recipes",
                "food",
                "pasta",
                "meal prep",
                "vegan",
                "breakfast",
            )
        ),
        "tech": sum(
            normalized.count(keyword)
            for keyword in (
                "gadgets",
                "tech",
                "ai",
                "saas",
                "automation",
                "tools",
                "notebook",
                "founder",
            )
        ),
        "lifestyle": sum(
            normalized.count(keyword)
            for keyword in (
                "lifestyle",
                "routine",
                "routines",
                "home decor",
                "decor",
                "cafe",
                "cafes",
                "cozy",
                "wellness",
                "journaling",
                "travel",
                "favorites",
            )
        ),
    }

    niche = max(niche_scores, key=niche_scores.get)
    if niche_scores[niche] == 0:
        niche = "other"

    sub_niches: list[str] = []
    if niche == "fitness":
        if "hyrox" in normalized:
            sub_niches.append("hyrox")
        if _contains_any(normalized, ("nutrition", "ernaehrung", "meal", "recovery")):
            sub_niches.append("nutrition")
        if "running" in normalized:
            sub_niches.append("running")
        if "strength" in normalized:
            sub_niches.append("strength")
        if "mobility" in normalized:
            sub_niches.append("mobility")
        if "workout" in normalized and "running" not in normalized and "strength" not in normalized:
            sub_niches.append("workouts")
    elif niche == "food":
        if _contains_any(normalized, ("rezepte", "recipes", "pasta")):
            sub_niches.append("recipes")
        if "meal prep" in normalized:
            sub_niches.append("meal-prep")
    elif niche == "tech":
        if "ai" in normalized:
            sub_niches.append("ai")
        if "saas" in normalized:
            sub_niches.append("saas")
        if "automation" in normalized:
            sub_niches.append("automation")
    elif niche == "lifestyle":
        if _contains_any(normalized, ("home decor", "decor")):
            sub_niches.append("home-decor")
        if _contains_any(normalized, ("nyc", "cafe", "cafes", "subway")):
            sub_niches.append("city-life")
        if "wellness" in normalized or "pilates" in normalized:
            sub_niches.append("wellness")
        if _contains_any(normalized, ("routine", "routines", "journaling")):
            sub_niches.append("routine")

    if not sub_niches:
        sub_niches = [niche if niche != "other" else "general"]

    return {
        "niche": niche,
        "sub_niches": list(dict.fromkeys(sub_niches)),
        "language": _detect_language(normalized),
        "brand_safety_score": 9 if niche in {"food", "lifestyle"} else 8,
        "reasoning": "Deterministic heuristic derived from bio, captions, and hashtags.",
    }


class HeuristicClassifierProvider(FakeLLMProvider):
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
        """Generate a deterministic classifier result from the input payload."""

        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "response_schema": response_schema,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        payload = json.loads(messages[-1].content)
        content = json.dumps(_derive_classifier_result(payload))
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=100,
            output_tokens=40,
            cost_usd=Decimal("0.0005"),
            raw_response={"content": content},
        )


def _build_evidence_claim(record: dict[str, Any]) -> str:
    """Derive a concise evidence claim from one content record."""

    if record.get("title"):
        return str(record["title"])
    if record.get("caption"):
        return str(record["caption"])
    brands = record.get("detected_brands") or []
    if brands:
        return f"Brand mention: {brands[0]}"
    return "Recent creator content observed."


class HeuristicEvidenceBuilderProvider(FakeLLMProvider):
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
        """Generate deterministic evidence items from the input payload."""

        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "response_schema": response_schema,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        payload = json.loads(messages[-1].content)
        recent_content = payload.get("recent_content", [])
        metrics = payload.get("metrics", {})
        sponsor_signal = max(
            [
                float(record.get("sponsor_probability") or 0.0)
                for record in recent_content
            ]
            + [0.85 if payload.get("existing_brands") else 0.0]
        )

        items: list[dict[str, object]] = []
        if payload.get("bio"):
            items.append(
                {
                    "claim_text": payload["bio"],
                    "source_uri": "bio",
                    "source_type": "bio",
                    "confidence": max(0.55, sponsor_signal, 0.65 if recent_content else 0.0),
                }
            )

        for record in recent_content:
            items.append(
                {
                    "claim_text": _build_evidence_claim(record),
                    "source_uri": record["source_uri"],
                    "source_type": record["source_type"],
                    "confidence": max(
                        0.65 if record.get("title") or record.get("caption") else 0.5,
                        float(record.get("sponsor_probability") or 0.0),
                        0.8 if record.get("detected_brands") else 0.0,
                    ),
                }
            )

        if metrics:
            items.append(
                {
                    "claim_text": (
                        f"Metrics snapshot for {payload['creator_handle']}: "
                        f"{metrics.get('followers', 'unknown')} followers."
                    ),
                    "source_uri": str(metrics.get("metrics_source_uri", "metrics")),
                    "source_type": "metric",
                    "confidence": max(0.6, sponsor_signal),
                }
            )

        content = json.dumps({"evidence_items": items})
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
