"""Golden-set tests for the evidence builder agent."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from ima.agents.evidence_builder.contract import (
    EVIDENCE_BUILDER_CONTRACT,
    EvidenceBuilderInput,
    EvidenceBuilderOutput,
)
from ima.agents.executor import AgentExecutor
from ima.db.session import get_session_factory
from ima.observability.langfuse_hook import LangfuseHook
from ima.providers.llm.anthropic_adapter import AnthropicAdapter
from ima.providers.llm.openai_adapter import OpenAIAdapter
from tests.conftest import FakeLangfuseHook, HeuristicEvidenceBuilderProvider


def _load_cases() -> list[dict[str, object]]:
    """Load YAML cases for parametrized testing."""

    cases_path = Path("tests/golden_sets/evidence_builder/cases.yaml")
    return yaml.safe_load(cases_path.read_text(encoding="utf-8"))


@pytest.mark.asyncio()
@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["case_id"])
async def test_evidence_builder_golden_set(case: dict[str, object], sqlite_session_factory) -> None:
    """Evidence builder should satisfy the curated golden-set expectations."""

    integration_mode = os.getenv("PYTEST_INTEGRATION", "false").lower() == "true"
    if integration_mode:
        providers = {
            "anthropic": AnthropicAdapter(),
            "openai": OpenAIAdapter(),
        }
        langfuse_hook = LangfuseHook()
    else:
        providers = {"mock": HeuristicEvidenceBuilderProvider()}
        langfuse_hook = FakeLangfuseHook()

    executor = AgentExecutor(
        contract=EVIDENCE_BUILDER_CONTRACT,
        llm_providers=providers,
        db_session_factory=(
            sqlite_session_factory if not integration_mode else get_session_factory()
        ),
        langfuse_hook=langfuse_hook,
    )

    output = await executor.run(EvidenceBuilderInput.model_validate(case["input"]))
    expected = case["expected"]

    assert len(output.evidence_items) >= expected["min_items"]
    assert all(item.confidence >= expected["min_confidence"] for item in output.evidence_items)
    assert all(item.source_uri for item in output.evidence_items)
    assert set(expected["required_source_types"]).issubset(
        {item.source_type for item in output.evidence_items}
    )

    if not integration_mode:
        provider = providers["mock"]
        assert len(provider.calls) == 1
        call = provider.calls[0]
        assert call["model"] == "claude-sonnet-4-6"
        assert call["response_schema"] is EvidenceBuilderOutput
        assert call["messages"][0].role == "system"
        assert (
            "Erfinde keine Quellen, keine Brands und keine Zahlen."
            in call["messages"][0].content
        )
        assert (
            "Gib ausschließlich eine gültige JSON-Struktur zurück."
            in call["messages"][0].content
        )
