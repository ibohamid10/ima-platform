"""Golden-set tests for the classifier agent."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from ima.agents.classifier.contract import CLASSIFIER_CONTRACT, ClassifierInput, ClassifierOutput
from ima.agents.executor import AgentExecutor
from ima.db.session import get_session_factory
from ima.observability.langfuse_hook import LangfuseHook
from ima.providers.llm.anthropic_adapter import AnthropicAdapter
from ima.providers.llm.openai_adapter import OpenAIAdapter
from tests.conftest import FakeLangfuseHook, HeuristicClassifierProvider


def _load_cases() -> list[dict[str, object]]:
    """Load YAML cases for parametrized testing."""

    cases_path = Path("tests/golden_sets/classifier/cases.yaml")
    return yaml.safe_load(cases_path.read_text(encoding="utf-8"))


@pytest.mark.asyncio()
@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["case_id"])
async def test_classifier_golden_set(case: dict[str, object], sqlite_session_factory) -> None:
    """Classifier should satisfy the curated golden-set expectations."""

    integration_mode = os.getenv("PYTEST_INTEGRATION", "false").lower() == "true"
    if integration_mode:
        providers = {
            "anthropic": AnthropicAdapter(),
            "openai": OpenAIAdapter(),
        }
        langfuse_hook = LangfuseHook()
    else:
        providers = {"mock": HeuristicClassifierProvider()}
        langfuse_hook = FakeLangfuseHook()

    executor = AgentExecutor(
        contract=CLASSIFIER_CONTRACT,
        llm_providers=providers,
        db_session_factory=sqlite_session_factory
        if not integration_mode
        else get_session_factory(),
        langfuse_hook=langfuse_hook,
    )

    output = await executor.run(ClassifierInput.model_validate(case["input"]))
    expected = case["expected"]
    assert output.niche == expected["niche"]
    assert set(expected["sub_niches"]).issubset(set(output.sub_niches))
    assert output.language == expected["language"]
    assert output.brand_safety_score >= expected["brand_safety_score_min"]

    if not integration_mode:
        provider = providers["mock"]
        assert len(provider.calls) == 1
        call = provider.calls[0]
        assert call["model"] == "claude-haiku-4-5-20251001"
        assert call["response_schema"] is ClassifierOutput
        assert call["messages"][0].role == "system"
        assert "bestimme die wahrscheinlichste Hauptnische" in call["messages"][0].content
        assert "Brand-Safety auf einer Skala von 0 bis 10" in call["messages"][0].content
