"""Run a week-2 smoke test across infrastructure, schema, and creator workflows."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import httpx
from db_migrate import main as migrate_main
from pydantic import BaseModel
from sqlalchemy import func, select

from ima.agents.evidence_builder.contract import EVIDENCE_BUILDER_CONTRACT, EvidenceBuilderOutput
from ima.agents.executor import AgentExecutor
from ima.config import settings
from ima.creators.classification import CreatorClassificationService
from ima.creators.scoring import CreatorScoringService
from ima.db.models import AgentRun, Creator, CreatorContent, EvidenceItem
from ima.db.session import get_session_factory
from ima.evidence.builder import EvidenceBuilderService
from ima.harvesters.pipeline import CreatorSourceImportService
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

    def start_trace(
        self,
        name: str,
        input_payload: dict[str, object],
        metadata: dict[str, object],
    ) -> SmokeTrace:
        """Return a no-op trace handle."""

        _ = (name, input_payload, metadata)
        return SmokeTrace()

    def start_generation(
        self,
        name: str,
        model: str,
        provider: str,
        input_payload: list[dict[str, str]],
    ) -> SmokeGeneration:
        """Return a no-op generation handle."""

        _ = (name, model, provider, input_payload)
        return SmokeGeneration()

    def flush(self) -> None:
        """No-op flush implementation."""


class SmokeDevelopmentProvider:
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
        """Return a deterministic structured response for classifier and evidence builder."""

        _ = (temperature, max_tokens)
        payload = json.loads(messages[-1].content)
        if response_schema is EvidenceBuilderOutput:
            items = []
            if payload.get("bio"):
                items.append(
                    {
                        "claim_text": payload["bio"],
                        "source_uri": "bio",
                        "source_type": "bio",
                        "confidence": 0.7,
                    }
                )
            for record in payload.get("recent_content", []):
                items.append(
                    {
                        "claim_text": record.get("title")
                        or record.get("caption")
                        or "Recent creator content observed.",
                        "source_uri": record["source_uri"],
                        "source_type": record["source_type"],
                        "confidence": 0.65,
                    }
                )
            if not items:
                items.append(
                    {
                        "claim_text": "Fallback metric evidence.",
                        "source_uri": payload["metrics"].get(
                            "metrics_source_uri",
                            "evidence://smoke/fallback",
                        ),
                        "source_type": "metric",
                        "confidence": 0.55,
                    }
                )
            content = json.dumps({"evidence_items": items})
        else:
            niche = "fitness" if "hyrox" in payload["bio"].lower() else "other"
            content = json.dumps(
                {
                    "niche": niche,
                    "sub_niches": ["hyrox", "nutrition"] if niche == "fitness" else [],
                    "language": "de",
                    "brand_safety_score": 9,
                    "reasoning": "Offline smoke-test provider.",
                }
            )
        return LLMResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            input_tokens=80,
            output_tokens=60,
            cost_usd=Decimal("0.0001"),
            raw_response={"content": content},
        )

    def supports_model(self, model: str) -> bool:
        """Return whether the smoke provider accepts the model."""

        return model in {
            "claude-haiku-4-5-20251001",
            "gpt-5.4-nano",
            "claude-sonnet-4-6",
            "gpt-5.4",
        }

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

    _, writer = await asyncio.open_connection(host, port)
    writer.close()
    await writer.wait_closed()


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


def _build_providers() -> dict[str, object]:
    """Build live or offline LLM providers for smoke execution."""

    providers: dict[str, object] = {}
    if settings.anthropic_api_key:
        providers["anthropic"] = AnthropicAdapter()
    if settings.openai_api_key:
        providers["openai"] = OpenAIAdapter()
    if not providers:
        providers["mock"] = SmokeDevelopmentProvider()
    return providers


async def _assert_columns(
    table_name: str,
    expected_columns: set[str],
    forbidden_columns: set[str] | None = None,
) -> None:
    """Validate that a table exists, exposes expected columns, and omits forbidden ones."""

    connection = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    try:
        rows = await connection.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            """,
            table_name,
        )
    finally:
        await connection.close()

    actual_columns = {row["column_name"] for row in rows}
    missing = expected_columns - actual_columns
    if missing:
        raise RuntimeError(f"{table_name} fehlt Spalten: {sorted(missing)}")
    forbidden = forbidden_columns or set()
    unexpected = forbidden & actual_columns
    if unexpected:
        raise RuntimeError(f"{table_name} enthaelt Legacy-Spalten: {sorted(unexpected)}")


async def run_creator_week2_smoke() -> None:
    """Run harvester, classifier, scoring, and evidence builder against local services."""

    providers = _build_providers()
    langfuse_hook = LangfuseHook() if settings.langfuse_enabled else SmokeLangfuseHook()
    source_import = CreatorSourceImportService(db_session_factory=get_session_factory())
    import_result = await source_import.import_fixture_file(
        Path("tests/fixtures/creator_source_batch.json"),
        via_temporal=False,
    )
    if import_result.imported_count < 1:
        raise RuntimeError("Fixture-Harvester hat keine Creator importiert.")
    creator_id = import_result.results[0].creator_id

    async with get_session_factory()() as session:
        creator = await session.get(Creator, creator_id)
        if creator is None:
            raise RuntimeError("Kein Creator nach Fixture-Import gefunden.")

        classifier_service = CreatorClassificationService(
            session=session,
            llm_providers=providers,
            db_session_factory=get_session_factory(),
            langfuse_hook=langfuse_hook,
        )
        await classifier_service.classify_creator_by_handle(
            platform=creator.platform,
            handle=creator.handle,
        )
        scoring_service = CreatorScoringService(session)
        await scoring_service.score_creator(str(creator.id))
        evidence_executor = AgentExecutor(
            contract=EVIDENCE_BUILDER_CONTRACT,
            llm_providers=providers,
            db_session_factory=get_session_factory(),
            langfuse_hook=langfuse_hook,
        )
        evidence_builder = EvidenceBuilderService(
            session,
            agent_executor=evidence_executor,
        )
        await evidence_builder.build_creator_evidence_by_handle(
            platform=creator.platform,
            handle=creator.handle,
        )
        await session.commit()

        creator_count = await session.scalar(select(func.count()).select_from(Creator))
        content_count = await session.scalar(select(func.count()).select_from(CreatorContent))
        evidence_count = await session.scalar(select(func.count()).select_from(EvidenceItem))
        latest_run = await session.scalar(
            select(AgentRun).order_by(AgentRun.started_at.desc()).limit(1)
        )

    if not creator_count or not content_count or not evidence_count:
        raise RuntimeError("Woche-2-Schemas wurden nicht mit Daten befuellt.")
    if latest_run is None:
        raise RuntimeError("Kein agent_run nach Classifier/Evidence-Builder gefunden.")


async def main() -> None:
    """Run the end-to-end week-2 smoke test."""

    try:
        redis_host, redis_port = _host_and_port_from_url(settings.redis_url, 6379)
        temporal_host, temporal_port = settings.temporal_address.split(":", maxsplit=1)
        await check_postgres()
        await check_tcp_port(redis_host, int(redis_port))
        await check_tcp_port(temporal_host, int(temporal_port))
        await check_http(f"{settings.qdrant_url}/readyz")
        await check_http(settings.effective_langfuse_base_url, optional=True)
        print("PASS: Infrastruktur erreichbar")

        await asyncio.to_thread(migrate_main)
        print("PASS: Alembic-Migration erfolgreich")

        await _assert_columns(
            "creators",
            {
                "id",
                "platform",
                "handle",
                "followers",
                "niche_labels",
                "language",
                "geo",
                "avg_views_30d",
                "avg_views_90d",
                "avg_engagement_30d",
                "growth_score",
                "niche_fit_score",
                "commercial_score",
                "fraud_score",
                "evidence_coverage_score",
                "email",
                "email_confidence",
                "consent_basis",
                "last_seen_at",
            },
            {"niche", "sub_niches"},
        )
        print("PASS: creators-Schema validiert")

        await _assert_columns(
            "creator_content",
            {
                "id",
                "creator_id",
                "published_at",
                "title",
                "caption",
                "hashtags",
                "view_count",
                "like_count",
                "comment_count",
                "detected_brands",
                "sponsor_probability",
                "raw_snapshot_uri",
            },
        )
        print("PASS: creator_content-Schema validiert")

        await _assert_columns(
            "evidence_items",
            {
                "id",
                "entity_type",
                "entity_id",
                "source_type",
                "source_uri",
                "claim_text",
                "confidence",
                "created_at",
            },
            {"evidence_type"},
        )
        print("PASS: evidence_items-Schema validiert")

        await run_creator_week2_smoke()
        print("PASS: Woche-2-Harvester/Scoring/Evidence-Pfad erfolgreich")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
