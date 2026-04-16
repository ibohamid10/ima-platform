"""Run a local week-1 smoke test across infrastructure and core runtime."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlparse

import asyncpg
import httpx
from pydantic import BaseModel
from sqlalchemy import select

from ima.agents.classifier.contract import CLASSIFIER_CONTRACT, ClassifierInput
from ima.agents.executor import AgentExecutor
from ima.config import settings
from ima.db.models import AgentRun
from ima.db.session import get_session_factory
from ima.observability.langfuse_hook import LangfuseHook
from ima.providers.llm.anthropic_adapter import AnthropicAdapter
from ima.providers.llm.base import LLMMessage, LLMResponse
from ima.providers.llm.openai_adapter import OpenAIAdapter


@dataclass
class SmokeTrace:
    """Simple no-op trace handle for offline smoke tests."""

    trace_id: str | None = "smoke-trace"
    trace_url: str | None = None

    def finish(self, **_: object) -> None:
        """No-op finish implementation."""


@dataclass
class SmokeGeneration:
    """Simple no-op generation handle for offline smoke tests."""

    trace_id: str | None = "smoke-trace"

    def update(self, **_: object) -> None:
        """No-op update implementation."""

    def finish(self) -> None:
        """No-op finish implementation."""


class SmokeLangfuseHook:
    """Fallback no-op Langfuse hook for offline smoke tests."""

    def start_trace(self, name: str, input_payload: dict[str, object], metadata: dict[str, object]) -> SmokeTrace:
        """Return a no-op trace handle."""

        _ = (name, input_payload, metadata)
        return SmokeTrace()

    def start_generation(
        self, name: str, model: str, provider: str, input_payload: list[dict[str, str]]
    ) -> SmokeGeneration:
        """Return a no-op generation handle."""

        _ = (name, model, provider, input_payload)
        return SmokeGeneration()

    def flush(self) -> None:
        """No-op flush implementation."""


class SmokeClassifierProvider:
    """Deterministic provider used when no live LLM credentials are present."""

    provider_name = "mock"

    async def complete(
        self,
        messages: list[LLMMessage],
        model: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Return a deterministic classifier response."""

        _ = (response_schema, temperature, max_tokens)
        payload = json.loads(messages[-1].content)
        niche = "fitness" if "hyrox" in payload["bio"].lower() else "other"
        content = json.dumps(
            {
                "niche": niche,
                "sub_niches": ["hyrox"] if niche == "fitness" else [],
                "language": "de",
                "brand_safety_score": 9,
                "reasoning": "Offline smoke-test provider.",
            }
        )
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=50,
            output_tokens=20,
            cost_usd=Decimal("0.0001"),
            raw_response={"content": content},
        )

    def supports_model(self, model: str) -> bool:
        """Return whether the smoke provider accepts the model."""

        return model in {"claude-haiku-4-5-20251001", "gpt-5.4-nano"}

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> Decimal:
        """Return a predictable fake cost."""

        _ = (input_tokens, output_tokens, model)
        return Decimal("0.0001")


async def check_postgres() -> None:
    """Ensure PostgreSQL is reachable."""

    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        await connection.fetchval("SELECT 1;")
    finally:
        await connection.close()


async def check_tcp_port(host: str, port: int) -> None:
    """Ensure a TCP service is reachable."""

    reader, writer = await asyncio.open_connection(host, port)
    writer.close()
    await writer.wait_closed()
    _ = reader


async def check_http(url: str, optional: bool = False) -> None:
    """Ensure an HTTP endpoint is reachable."""

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except Exception:
            if optional:
                print(f"OPTIONAL service not reachable: {url}")
                return
            raise


def _host_and_port_from_url(url: str, default_port: int) -> tuple[str, int]:
    """Return host and port extracted from a URL-like setting."""

    parsed = urlparse(url)
    return parsed.hostname or "localhost", parsed.port or default_port


async def run_classifier_smoke() -> None:
    """Run the classifier and assert that an agent_run is persisted."""

    langfuse_hook = LangfuseHook() if settings.langfuse_enabled else SmokeLangfuseHook()
    if settings.anthropic_api_key or settings.openai_api_key:
        providers = {
            "anthropic": AnthropicAdapter(),
            "openai": OpenAIAdapter(),
        }
    else:
        providers = {"mock": SmokeClassifierProvider()}

    executor = AgentExecutor(
        contract=CLASSIFIER_CONTRACT,
        llm_providers=providers,
        db_session_factory=get_session_factory(),
        langfuse_hook=langfuse_hook,
    )
    await executor.run(
        ClassifierInput(
            creator_handle="fitnessfranz",
            platform="youtube",
            bio="Hyrox Athlet aus Wien | Training und Ernaehrung",
            recent_captions=["Neues Hyrox-PR-Video ist online!"],
            top_hashtags=["#hyrox", "#fitness"],
        )
    )
    async with get_session_factory()() as session:
        run = await session.scalar(
            select(AgentRun).order_by(AgentRun.started_at.desc()).limit(1)
        )
    if run is None:
        raise RuntimeError("Kein agent_run wurde in Postgres gefunden.")


async def main() -> None:
    """Run the end-to-end smoke test."""

    try:
        redis_host, redis_port = _host_and_port_from_url(settings.redis_url, 6379)
        temporal_host, temporal_port = settings.temporal_address.split(":", maxsplit=1)
        await check_postgres()
        await check_tcp_port(redis_host, int(redis_port))
        await check_tcp_port(temporal_host, int(temporal_port))
        await check_http(f"{settings.qdrant_url}/readyz")
        await check_http(settings.effective_langfuse_base_url, optional=True)
        print("PASS: Infrastruktur erreichbar")

        from db_migrate import main as migrate_main

        await migrate_main()
        print("PASS: Migration erfolgreich")

        await run_classifier_smoke()
        print("PASS: Classifier-End-to-End erfolgreich")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
