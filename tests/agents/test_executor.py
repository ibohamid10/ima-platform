"""Unit tests for the AgentExecutor runtime."""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal

import pytest
from sqlalchemy import select

from ima.agents.classifier.contract import CLASSIFIER_CONTRACT, ClassifierInput
from ima.agents.exceptions import AgentProviderSelectionError
from ima.agents.executor import AgentExecutor
from ima.config import settings
from ima.db.models import AgentRun, ValidationStatus
from ima.providers.llm.base import LLMMessage, LLMResponse
from ima.providers.llm.exceptions import (
    LLMBudgetExceededError,
    LLMSchemaValidationAttemptsError,
    LLMSchemaValidationError,
)


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
    assert run.reserved_cost_usd == Decimal("0")


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
    assert run.validation_attempts == 2


@pytest.mark.asyncio()
async def test_executor_schema_fail_persists_actual_attempt_count(
    sqlite_session_factory, fake_langfuse_hook, monkeypatch
) -> None:
    """Schema-failed telemetry should use the attempt count carried by the error."""

    from tests.conftest import FakeLLMProvider

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

    async def fail_with_three_attempts(**_: object) -> tuple[object, object, int]:
        raise LLMSchemaValidationAttemptsError("Schema failed after three attempts.", attempts=3)

    monkeypatch.setattr(executor, "_attempt_completion", fail_with_three_attempts)

    with pytest.raises(LLMSchemaValidationAttemptsError):
        await executor.run(
            ClassifierInput(
                creator_handle="three-attempt-case",
                platform="instagram",
                bio="Coach",
                recent_captions=["Caption"],
                top_hashtags=["#fitness"],
            )
        )

    async with sqlite_session_factory() as session:
        run = await session.scalar(select(AgentRun))
    assert run is not None
    assert run.validation_status == ValidationStatus.SCHEMA_FAILED.value
    assert run.validation_attempts == 3


@pytest.mark.asyncio()
async def test_executor_budget_exceeded(sqlite_session_factory, fake_langfuse_hook) -> None:
    """Budget exhaustion should still write an agent_run audit record."""

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
    async with sqlite_session_factory() as session:
        runs = list((await session.scalars(select(AgentRun).order_by(AgentRun.started_at))).all())
    assert len(runs) == 2
    run = runs[-1]
    assert run.validation_status == ValidationStatus.BUDGET_EXCEEDED.value
    assert run.error_message == "Das taegliche LLM-Budget ist bereits ausgeschoepft."
    assert run.output_json is None
    assert run.completed_at is not None
    assert run.reserved_cost_usd == Decimal("0")


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


@pytest.mark.asyncio()
async def test_executor_provider_selection_failure_writes_agent_run(
    sqlite_session_factory, fake_langfuse_hook
) -> None:
    """Missing compatible providers should still create an audited failed run."""

    from tests.conftest import FakeLLMProvider

    provider = FakeLLMProvider(
        provider_name="mock",
        supported_models={"some-other-model"},
        responses=[],
    )
    executor = AgentExecutor(
        contract=CLASSIFIER_CONTRACT,
        llm_providers={"mock": provider},
        db_session_factory=sqlite_session_factory,
        langfuse_hook=fake_langfuse_hook,
    )

    with pytest.raises(AgentProviderSelectionError):
        await executor.run(
            ClassifierInput(
                creator_handle="selectioncase",
                platform="youtube",
                bio="No matching model available",
                recent_captions=["Caption"],
                top_hashtags=["#test"],
            )
        )

    assert provider.calls == []
    async with sqlite_session_factory() as session:
        run = await session.scalar(select(AgentRun))
    assert run is not None
    assert run.validation_status == ValidationStatus.PROVIDER_UNAVAILABLE.value
    assert run.error_message == (
        "Kein Provider unterstuetzt Modelle ['claude-haiku-4-5-20251001', 'gpt-5.4-nano']."
    )
    assert run.output_json is None
    assert run.completed_at is not None
    assert run.reserved_cost_usd == Decimal("0")


@pytest.mark.asyncio()
async def test_executor_budget_reservation_blocks_second_pending_run(
    sqlite_session_factory, fake_langfuse_hook, monkeypatch
) -> None:
    """An in-flight reservation should count against the daily budget immediately."""

    class BlockingProvider:
        provider_name = "mock"

        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.calls: list[dict[str, object]] = []

        async def complete(
            self,
            messages: list[LLMMessage],
            model: str,
            response_schema=None,
            temperature: float = 0.7,
            max_tokens: int = 4096,
        ) -> LLMResponse:
            self.calls.append(
                {
                    "messages": messages,
                    "model": model,
                    "response_schema": response_schema,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            )
            self.started.set()
            await self.release.wait()
            return LLMResponse(
                content=json.dumps(
                    {
                        "niche": "fitness",
                        "sub_niches": ["hyrox"],
                        "language": "de",
                        "brand_safety_score": 8,
                        "reasoning": "Released after reservation test.",
                    }
                ),
                model=model,
                provider=self.provider_name,
                input_tokens=100,
                output_tokens=50,
                cost_usd=Decimal("0.001000"),
                raw_response={"content": "released"},
            )

        def supports_model(self, model: str) -> bool:
            return model == "claude-haiku-4-5-20251001"

        def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> Decimal:
            _ = (input_tokens, output_tokens, model)
            return Decimal("0.001000")

    monkeypatch.setattr(settings, "llm_daily_budget_usd", 0.0015)
    provider = BlockingProvider()
    executor = AgentExecutor(
        contract=CLASSIFIER_CONTRACT,
        llm_providers={"mock": provider},
        db_session_factory=sqlite_session_factory,
        langfuse_hook=fake_langfuse_hook,
    )
    first_input = ClassifierInput(
        creator_handle="first-budget-run",
        platform="youtube",
        bio="Hyrox Athlet",
        recent_captions=["Caption"],
        top_hashtags=["#fitness"],
    )
    second_input = ClassifierInput(
        creator_handle="second-budget-run",
        platform="youtube",
        bio="Hyrox Athlet",
        recent_captions=["Caption"],
        top_hashtags=["#fitness"],
    )

    first_task = asyncio.create_task(executor.run(first_input))
    await provider.started.wait()

    with pytest.raises(LLMBudgetExceededError):
        await executor.run(second_input)

    provider.release.set()
    first_output = await first_task

    assert first_output.niche == "fitness"
    assert len(provider.calls) == 1
    async with sqlite_session_factory() as session:
        runs = list(
            (
                await session.scalars(
                    select(AgentRun).order_by(AgentRun.started_at, AgentRun.id)
                )
            ).all()
        )
    assert len(runs) == 2
    assert runs[0].validation_status == ValidationStatus.SUCCESS.value
    assert runs[0].reserved_cost_usd == Decimal("0")
    assert runs[1].validation_status == ValidationStatus.BUDGET_EXCEEDED.value
    assert runs[1].reserved_cost_usd == Decimal("0")
