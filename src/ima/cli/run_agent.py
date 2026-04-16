"""CLI entry point for running local agents."""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path

import typer
from pydantic import BaseModel

from ima.agents.classifier.contract import CLASSIFIER_CONTRACT, ClassifierInput
from ima.agents.executor import AgentExecutor
from ima.config import settings
from ima.db.session import get_session_factory
from ima.observability.langfuse_hook import LangfuseHook
from ima.providers.llm.anthropic_adapter import AnthropicAdapter
from ima.providers.llm.base import LLMMessage, LLMResponse
from ima.providers.llm.openai_adapter import OpenAIAdapter

app = typer.Typer(help="CLI for local IMA agent execution.")
run_agent_app = typer.Typer(help="Run a specific agent contract.")
app.add_typer(run_agent_app, name="run-agent")


class OfflineClassifierProvider:
    """Deterministic local fallback when no LLM credentials are configured."""

    provider_name = "offline"

    def supports_model(self, model: str) -> bool:
        """Return whether the provider can emulate the requested model."""

        return model in {"claude-haiku-4-5-20251001", "gpt-5.4-nano", "gpt-5.4-mini", "gpt-5.4"}

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> Decimal:
        """Return a fixed low development-only cost."""

        _ = (input_tokens, output_tokens, model)
        return Decimal("0.0001")

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a deterministic classifier output from the input payload."""

        _ = (response_schema, temperature, max_tokens)
        payload = json.loads(messages[-1].content)
        text = " ".join(
            [
                payload.get("bio", ""),
                " ".join(payload.get("recent_captions", [])),
                " ".join(payload.get("top_hashtags", [])),
            ]
        ).lower()

        niche = "other"
        sub_niches: list[str] = []
        if any(token in text for token in ("hyrox", "fitness", "workout", "running", "pilates")):
            niche = "fitness"
            sub_niches = [token for token in ["hyrox", "running", "pilates", "nutrition"] if token in text]
        elif any(token in text for token in ("saas", "ai", "tech", "automation", "gadget")):
            niche = "tech"
            sub_niches = [token for token in ["saas", "ai", "automation", "gadgets"] if token in text]
        elif any(token in text for token in ("recipe", "rezepte", "food", "meal prep", "pasta")):
            niche = "food"
            sub_niches = [token for token in ["recipes", "meal-prep", "nutrition"] if token in text]
        elif any(token in text for token in ("lifestyle", "decor", "cafe", "morning routine", "wellness")):
            niche = "lifestyle"
            sub_niches = [token for token in ["wellness", "home-decor", "city-life", "routine"] if token in text]

        language = "de" if any(token in text for token in ("wien", "deutsch", "ernaehrung", "heute")) else "en"
        safety = 9
        if any(token in text for token in ("politik", "political", "controvers", "kontroverse", "media luegen")):
            safety = 2
        if any(token in text for token in ("explicit", "adult", "nsfw", "shock humor")):
            safety = 1

        content = json.dumps(
            {
                "niche": niche,
                "sub_niches": sub_niches,
                "language": language,
                "brand_safety_score": safety,
                "reasoning": "Offline fallback based on simple heuristics for local development.",
            }
        )
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=120,
            output_tokens=50,
            cost_usd=Decimal("0.0001"),
            raw_response={"content": content},
        )


def _build_llm_providers() -> dict[str, object]:
    """Build provider adapters, including an offline fallback for local development."""

    providers: dict[str, object] = {}
    if settings.anthropic_api_key:
        providers["anthropic"] = AnthropicAdapter()
    if settings.openai_api_key:
        providers["openai"] = OpenAIAdapter()
    if not providers:
        providers["offline"] = OfflineClassifierProvider()
    return providers


async def _run_classifier(input_file: Path) -> None:
    """Run the classifier agent for the given JSON input file."""

    payload = json.loads(input_file.read_text(encoding="utf-8"))
    inputs = ClassifierInput.model_validate(payload)
    executor = AgentExecutor(
        contract=CLASSIFIER_CONTRACT,
        llm_providers=_build_llm_providers(),
        db_session_factory=get_session_factory(),
        langfuse_hook=LangfuseHook(),
    )
    output = await executor.run(inputs)
    typer.echo(json.dumps(output.model_dump(mode="json"), indent=2, ensure_ascii=False))
    if executor.last_run_info is not None:
        typer.echo(f"cost_usd={executor.last_run_info['cost_usd']}")
        typer.echo(f"latency_ms={executor.last_run_info['latency_ms']}")
        if executor.last_run_info.get("trace_url"):
            typer.echo(f"langfuse_trace={executor.last_run_info['trace_url']}")


@run_agent_app.command("classifier")
def run_classifier(input_file: Path = typer.Option(..., "--input-file", exists=True, readable=True)) -> None:
    """Run the classifier agent against an input JSON file."""

    asyncio.run(_run_classifier(input_file))


def main() -> None:
    """Execute the Typer application."""

    app()
