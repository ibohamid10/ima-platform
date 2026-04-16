"""Unit tests for the AgentExecutor runtime."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import select

from ima.agents.classifier.contract import CLASSIFIER_CONTRACT, ClassifierInput
from ima.agents.executor import AgentExecutor
from ima.db.models import AgentRun
from ima.providers.llm.exceptions import LLMBudgetExceededError, LLMSchemaValidationError


@pytest.mark.asyncio()
async def test_executor_happy_path(sqlite_session_factory, fake_langfuse_hook) -> None:
    """A valid response should produce a successful agent_run record."""

    from tests.conftest import FakeLLMProvider

    provider = FakeLLMProvider(
        provider_name="mock",
        supported_models={"claude-haiku-4-5-20251001"},
        responses=[
            json.dumps(
                {
                    "niche": "fitness",
                    "sub_niches": ["hyrox"],
                    "language": "de",
                    "brand_safety_score": 9,
                    "reasoning": "Clean sports profile.",
                }
            )
        ],
    )
    executor = AgentExecutor(
        contract=CLASSIFIER_CONTRACT,
        llm_providers={"mock": provider},
        db_session_factory=sqlite_session_factory,
        langfuse_hook=fake_langfuse_hook,
    )

    output = await executor.run(
        ClassifierInput(
            creator_handle="fitnessfranz",
            platform="youtube",
            bio="Hyrox Athlet",
            recent_captions=["Schneller Lauf"],
            top_hashtags=["#fitness"],
        )
    )

    assert output.niche == "fitness"
    async with sqlite_session_factory() as session:
        run = await session.scalar(select(AgentRun))
    assert run is not None
    assert run.validation_status == "success"
    assert run.output_json is not None


@pytest.mark.asyncio()
async def test_executor_schema_retry(sqlite_session_factory, fake_langfuse_hook) -> None:
    """The executor should retry once after a schema validation failure."""

    from tests.conftest import FakeLLMProvider

    provider = FakeLLMProvider(
        provider_name="mock",
        supported_models={"claude-haiku-4-5-20251001"},
        responses=[
            '{"niche":"fitness"}',
            json.dumps(
                {
                    "niche": "fitness",
                    "sub_niches": ["hyrox"],
                    "language": "de",
                    "brand_safety_score": 8,
                    "reasoning": "Retry succeeded.",
                }
            ),
        ],
    )
    executor = AgentExecutor(
        contract=CLASSIFIER_CONTRACT,
        llm_providers={"mock": provider},
        db_session_factory=sqlite_session_factory,
        langfuse_hook=fake_langfuse_hook,
    )

    output = await executor.run(
        ClassifierInput(
            creator_handle="retrycase",
            platform="instagram",
            bio="Coach",
            recent_captions=["Caption"],
            top_hashtags=["#fitness"],
        )
    )

    assert output.brand_safety_score == 8
    async with sqlite_session_factory() as session:
        run = await session.scalar(select(AgentRun))
    assert run is not None
    assert run.validation_attempts == 2


@pytest.mark.asyncio()
async def test_executor_schema_fail(sqlite_session_factory, fake_langfuse_hook) -> None:
    """Two invalid outputs should raise LLMSchemaValidationError."""

    from tests.conftest import FakeLLMProvider

    provider = FakeLLMProvider(
        provider_name="mock",
        supported_models={"claude-haiku-4-5-20251001"},
        responses=['{"niche":"fitness"}', '{"language":"de"}'],
    )
    executor = AgentExecutor(
        contract=CLASSIFIER_CONTRACT,
        llm_providers={"mock": provider},
        db_session_factory=sqlite_session_factory,
        langfuse_hook=fake_langfuse_hook,
    )

    with pytest.raises(LLMSchemaValidationError):
        await executor.run(
            ClassifierInput(
                creator_handle="failcase",
                platform="instagram",
                bio="Coach",
                recent_captions=["Caption"],
                top_hashtags=["#fitness"],
            )
        )

    async with sqlite_session_factory() as session:
        run = await session.scalar(select(AgentRun))
    assert run is not None
    assert run.validation_status == "schema_failed"


@pytest.mark.asyncio()
async def test_executor_budget_exceeded(sqlite_session_factory, fake_langfuse_hook) -> None:
    """Budget exhaustion should fail before hitting the provider."""

    from tests.conftest import FakeLLMProvider

    async with sqlite_session_factory() as session:
        session.add(
            AgentRun(
                agent_name="classifier",
                contract_version="1.0.0",
                provider="mock",
                model="claude-haiku-4-5-20251001",
                input_hash="x" * 64,
                input_json={"seed": True},
                output_json={"ok": True},
                validation_status="success",
                validation_attempts=1,
                input_tokens=10,
                output_tokens=10,
                cost_usd=Decimal("999.000000"),
                latency_ms=10,
            )
        )
        await session.commit()

    provider = FakeLLMProvider(
        provider_name="mock",
        supported_models={"claude-haiku-4-5-20251001"},
        responses=[],
    )
    executor = AgentExecutor(
        contract=CLASSIFIER_CONTRACT,
        llm_providers={"mock": provider},
        db_session_factory=sqlite_session_factory,
        langfuse_hook=fake_langfuse_hook,
    )

    with pytest.raises(LLMBudgetExceededError):
        await executor.run(
            ClassifierInput(
                creator_handle="budgetcase",
                platform="youtube",
                bio="Budget",
                recent_captions=["Caption"],
                top_hashtags=["#test"],
            )
        )
    assert provider.calls == []


@pytest.mark.asyncio()
async def test_executor_provider_fallback(sqlite_session_factory, fake_langfuse_hook) -> None:
    """Provider fallback should use the next compatible provider when the first is unavailable."""

    from tests.conftest import FakeLLMProvider

    unavailable = FakeLLMProvider(
        provider_name="anthropic",
        supported_models={"claude-haiku-4-5-20251001"},
        unavailable=True,
    )
    fallback = FakeLLMProvider(
        provider_name="openai",
        supported_models={"claude-haiku-4-5-20251001"},
        responses=[
            json.dumps(
                {
                    "niche": "tech",
                    "sub_niches": ["saas"],
                    "language": "en",
                    "brand_safety_score": 9,
                    "reasoning": "Fallback provider worked.",
                }
            )
        ],
    )
    executor = AgentExecutor(
        contract=CLASSIFIER_CONTRACT,
        llm_providers={"anthropic": unavailable, "openai": fallback},
        db_session_factory=sqlite_session_factory,
        langfuse_hook=fake_langfuse_hook,
    )

    output = await executor.run(
        ClassifierInput(
            creator_handle="fallbackcase",
            platform="youtube",
            bio="SaaS builder",
            recent_captions=["Shipping product updates"],
            top_hashtags=["#saas"],
        )
    )

    assert output.niche == "tech"
    assert len(unavailable.calls) == 1
    assert len(fallback.calls) == 1
