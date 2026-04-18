"""CLI entry point for running local agents and week-2 creator workflows."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from pydantic import BaseModel
from sqlalchemy import select
from temporalio.common import WorkflowIDConflictPolicy

from ima.agents.classifier.contract import CLASSIFIER_CONTRACT, ClassifierInput
from ima.agents.evidence_builder.contract import (
    EVIDENCE_BUILDER_CONTRACT,
    EvidenceBuilderOutput,
)
from ima.agents.executor import AgentExecutor
from ima.brands.enricher import BrandEnricher
from ima.brands.seeder import BrandSeeder
from ima.brands.service import BrandService
from ima.brands.spend_intent import BrandSpendIntentScorer
from ima.config import settings
from ima.creators.classification import CreatorClassificationService
from ima.creators.ingest import CreatorIngestService
from ima.creators.schemas import CreatorGrowthSnapshotInput, CreatorIngestInput, CreatorIngestResult
from ima.creators.scoring import CreatorScoringService
from ima.db.models import Brand, Creator
from ima.db.session import get_session_factory
from ima.evidence.builder import EvidenceBuilderService
from ima.harvesters.pipeline import CreatorSourceImportService
from ima.harvesters.schemas import YouTubeChannelHarvestRequest, YouTubeKeywordDiscoveryRequest
from ima.harvesters.youtube_data_api import YouTubeDataAPIHarvester
from ima.niches import get_niche_registry
from ima.observability.langfuse_hook import LangfuseHook
from ima.providers.llm.anthropic_adapter import AnthropicAdapter
from ima.providers.llm.base import LLMMessage, LLMResponse
from ima.providers.llm.openai_adapter import OpenAIAdapter
from ima.temporal.client import get_temporal_client
from ima.temporal.constants import CREATOR_INGEST_WORKFLOW, CREATOR_TASK_QUEUE
from ima.temporal.worker import run_creator_worker

app = typer.Typer(help="CLI for local IMA agent execution.")
run_agent_app = typer.Typer(help="Run a specific agent contract.")
creator_app = typer.Typer(help="Creator growth tracking and scoring tools.")
brand_app = typer.Typer(help="Brand seeding, enrichment, and spend-intent tools.")
evidence_app = typer.Typer(help="Evidence building and evidence storage tools.")
temporal_app = typer.Typer(help="Temporal worker and workflow tools.")
app.add_typer(run_agent_app, name="run-agent")
app.add_typer(creator_app, name="creators")
app.add_typer(brand_app, name="brands")
app.add_typer(evidence_app, name="evidence")
app.add_typer(temporal_app, name="temporal")


class OfflineDevelopmentProvider:
    """Deterministic local fallback when no live LLM credentials are configured."""

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
        """Generate deterministic structured outputs for local development."""

        _ = (response_schema, temperature, max_tokens)
        payload = json.loads(messages[-1].content)
        if response_schema is EvidenceBuilderOutput:
            items: list[dict[str, object]] = []
            if payload.get("bio"):
                items.append(
                    {
                        "claim_text": payload["bio"],
                        "source_uri": "bio",
                        "source_type": "bio",
                        "confidence": 0.65,
                    }
                )
            for content in payload.get("recent_content", []):
                items.append(
                    {
                        "claim_text": content.get("title")
                        or content.get("caption")
                        or "Recent creator content observed.",
                        "source_uri": content["source_uri"],
                        "source_type": content["source_type"],
                        "confidence": max(content.get("sponsor_probability") or 0.55, 0.55),
                    }
                )
            if not items:
                items.append(
                    {
                        "claim_text": f"Creator {payload['creator_handle']} has limited evidence.",
                        "source_uri": payload["metrics"].get(
                            "metrics_source_uri",
                            "evidence://offline/metrics",
                        ),
                        "source_type": "metric",
                        "confidence": 0.5,
                    }
                )
            content = json.dumps({"evidence_items": items})
            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider_name,
                input_tokens=140,
                output_tokens=110,
                cost_usd=Decimal("0.0002"),
                raw_response={"content": content},
            )

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
            sub_niches = [
                token for token in ["hyrox", "running", "pilates", "nutrition"] if token in text
            ]
        elif any(token in text for token in ("saas", "ai", "tech", "automation", "gadget")):
            niche = "tech"
            sub_niches = [
                token for token in ["saas", "ai", "automation", "gadgets"] if token in text
            ]
        elif any(token in text for token in ("recipe", "rezepte", "food", "meal prep", "pasta")):
            niche = "food"
            sub_niches = [token for token in ["recipes", "meal-prep", "nutrition"] if token in text]
        elif any(
            token in text for token in ("lifestyle", "decor", "cafe", "morning routine", "wellness")
        ):
            niche = "lifestyle"
            sub_niches = [
                token
                for token in ["wellness", "home-decor", "city-life", "routine"]
                if token in text
            ]

        language = (
            "de"
            if any(token in text for token in ("wien", "deutsch", "ernaehrung", "heute"))
            else "en"
        )
        safety = 9
        if any(
            token in text
            for token in ("politik", "political", "controvers", "kontroverse", "media luegen")
        ):
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
        providers["offline"] = OfflineDevelopmentProvider()
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
def run_classifier(
    input_file: Annotated[
        Path,
        typer.Option("--input-file", exists=True, readable=True),
    ],
) -> None:
    """Run the classifier agent against an input JSON file."""

    asyncio.run(_run_classifier(input_file))


def main() -> None:
    """Execute the Typer application."""

    app()


def _parse_captured_at(captured_at: str | None) -> datetime | None:
    """Parse ISO timestamps for creator snapshot ingestion."""

    if captured_at is None:
        return None

    normalized = captured_at.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise typer.BadParameter(
            "--captured-at muss ISO-8601 sein, z.B. 2026-03-15T10:00:00+00:00."
        ) from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


@creator_app.command("score")
def score_creator(
    handle: str = typer.Option(..., "--handle"),
    platform: str = typer.Option(..., "--platform"),
) -> None:
    """Score one creator by platform and handle."""

    asyncio.run(_score_creator(handle=handle, platform=platform))


async def _score_creator(handle: str, platform: str) -> None:
    """Load one creator and print the current scoring result as JSON."""

    async with get_session_factory()() as session:
        service = CreatorScoringService(session)
        result = await service.score_creator_by_handle(platform=platform, handle=handle)
        await session.commit()
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


@creator_app.command("classify")
def classify_creator(
    handle: str = typer.Option(..., "--handle"),
    platform: str = typer.Option(..., "--platform"),
) -> None:
    """Run the classifier for one stored creator and persist `niche_labels`."""

    asyncio.run(_classify_creator(handle=handle, platform=platform))


async def _classify_creator(handle: str, platform: str) -> None:
    """Load a creator, classify it, and persist the classifier output."""

    async with get_session_factory()() as session:
        service = CreatorClassificationService(
            session=session,
            llm_providers=_build_llm_providers(),
            db_session_factory=get_session_factory(),
            langfuse_hook=LangfuseHook(),
        )
        result = await service.classify_creator_by_handle(platform=platform, handle=handle)
        await session.commit()
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


@creator_app.command("record-snapshot")
def record_snapshot(
    handle: str = typer.Option(..., "--handle"),
    platform: str = typer.Option(..., "--platform"),
    captured_at: str | None = typer.Option(None, "--captured-at"),
    follower_count: int | None = typer.Option(None, "--follower-count"),
    average_views_30d: int | None = typer.Option(None, "--average-views-30d"),
    average_likes_30d: int | None = typer.Option(None, "--average-likes-30d"),
    average_comments_30d: int | None = typer.Option(None, "--average-comments-30d"),
    engagement_rate_30d: float | None = typer.Option(None, "--engagement-rate-30d"),
    source: str = typer.Option("manual", "--source"),
) -> None:
    """Persist one creator metric snapshot for local development."""

    asyncio.run(
        _record_snapshot(
            handle=handle,
            platform=platform,
            captured_at=_parse_captured_at(captured_at),
            follower_count=follower_count,
            average_views_30d=average_views_30d,
            average_likes_30d=average_likes_30d,
            average_comments_30d=average_comments_30d,
            engagement_rate_30d=engagement_rate_30d,
            source=source,
        )
    )


async def _record_snapshot(
    handle: str,
    platform: str,
    captured_at: datetime | None,
    follower_count: int | None,
    average_views_30d: int | None,
    average_likes_30d: int | None,
    average_comments_30d: int | None,
    engagement_rate_30d: float | None,
    source: str,
) -> None:
    """Resolve a creator and store one metric snapshot."""

    async with get_session_factory()() as session:
        creator = await session.scalar(
            select(Creator).where(Creator.platform == platform, Creator.handle == handle)
        )
        if creator is None:
            raise typer.BadParameter(f"Creator {platform}/{handle} wurde nicht gefunden.")

        service = CreatorScoringService(session)
        snapshot = await service.record_snapshot(
            CreatorGrowthSnapshotInput(
                creator_id=str(creator.id),
                captured_at=captured_at or datetime.now(UTC),
                followers=follower_count,
                average_views_30d=average_views_30d,
                average_likes_30d=average_likes_30d,
                average_comments_30d=average_comments_30d,
                engagement_rate_30d=(
                    Decimal(str(engagement_rate_30d)) if engagement_rate_30d is not None else None
                ),
                source=source,
            )
        )
        await session.commit()
    typer.echo(
        json.dumps(
            {
                "snapshot_id": str(snapshot.id),
                "creator_id": str(snapshot.creator_id),
                "captured_at": snapshot.captured_at.isoformat(),
                "source": snapshot.source,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


@creator_app.command("ingest")
def ingest_creator(
    input_file: Annotated[
        Path,
        typer.Option("--input-file", exists=True, readable=True),
    ],
) -> None:
    """Ingest one creator payload from JSON, then snapshot and score it."""

    asyncio.run(_ingest_creator(input_file))


async def _ingest_creator(input_file: Path) -> None:
    """Read one ingest payload from disk and execute the local ingest pipeline."""

    payload = CreatorIngestInput.model_validate_json(input_file.read_text(encoding="utf-8"))
    async with get_session_factory()() as session:
        service = CreatorIngestService(session)
        result = await service.ingest(payload)
        await session.commit()
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


@creator_app.command("import-source-batch")
def import_source_batch(
    input_file: Annotated[
        Path,
        typer.Option("--input-file", exists=True, readable=True),
    ],
    via_temporal: bool = typer.Option(True, "--via-temporal/--direct"),
    workflow_prefix: str = typer.Option("creator-source-import", "--workflow-prefix"),
    task_queue: str = typer.Option(CREATOR_TASK_QUEUE, "--task-queue"),
) -> None:
    """Import one fixture-based source batch through direct or Temporal ingest."""

    asyncio.run(
        _import_source_batch(
            input_file=input_file,
            via_temporal=via_temporal,
            workflow_prefix=workflow_prefix,
            task_queue=task_queue,
        )
    )


async def _import_source_batch(
    input_file: Path,
    via_temporal: bool,
    workflow_prefix: str,
    task_queue: str,
) -> None:
    """Load one fixture source batch and route it into the canonical ingest path."""

    service = CreatorSourceImportService()
    result = await service.import_fixture_file(
        input_file,
        via_temporal=via_temporal,
        workflow_prefix=workflow_prefix,
        task_queue=task_queue,
    )
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


@creator_app.command("import-youtube-channel")
def import_youtube_channel(
    channel_id: str = typer.Option(..., "--channel-id"),
    max_videos: int = typer.Option(5, "--max-videos"),
    via_temporal: bool = typer.Option(True, "--via-temporal/--direct"),
    workflow_prefix: str = typer.Option("youtube-channel", "--workflow-prefix"),
    task_queue: str = typer.Option(CREATOR_TASK_QUEUE, "--task-queue"),
) -> None:
    """Harvest one YouTube channel by channel ID and import it through canonical ingest."""

    asyncio.run(
        _import_youtube_channel(
            channel_id=channel_id,
            max_videos=max_videos,
            via_temporal=via_temporal,
            workflow_prefix=workflow_prefix,
            task_queue=task_queue,
        )
    )


@creator_app.command("discover-youtube")
def discover_youtube(
    keywords: str | None = typer.Option(None, "--keywords"),
    niche: str | None = typer.Option(None, "--niche"),
    language: str | None = typer.Option(None, "--language"),
    region: str | None = typer.Option(None, "--region"),
    min_subscribers: int | None = typer.Option(None, "--min-subscribers"),
    max_subscribers: int | None = typer.Option(None, "--max-subscribers"),
    max_results_per_keyword: int = typer.Option(5, "--max-results-per-keyword"),
    max_videos: int = typer.Option(5, "--max-videos"),
    via_temporal: bool = typer.Option(True, "--via-temporal/--direct"),
    workflow_prefix: str = typer.Option("youtube-discovery", "--workflow-prefix"),
    task_queue: str = typer.Option(CREATOR_TASK_QUEUE, "--task-queue"),
) -> None:
    """Discover YouTube channels from keywords and send them through canonical ingest."""

    asyncio.run(
        _discover_youtube(
            keywords=keywords,
            niche=niche,
            language=language,
            region=region,
            min_subscribers=min_subscribers,
            max_subscribers=max_subscribers,
            max_results_per_keyword=max_results_per_keyword,
            max_videos=max_videos,
            via_temporal=via_temporal,
            workflow_prefix=workflow_prefix,
            task_queue=task_queue,
        )
    )


async def _import_youtube_channel(
    channel_id: str,
    max_videos: int,
    via_temporal: bool,
    workflow_prefix: str,
    task_queue: str,
) -> None:
    """Harvest one YouTube channel from the live API and send it into source import."""

    request = YouTubeChannelHarvestRequest(
        channel_id=channel_id,
        max_videos=max_videos,
        source_labels=["youtube_live_import"],
    )
    harvested_record = await YouTubeDataAPIHarvester().harvest_channel(request)
    result = await CreatorSourceImportService().import_records(
        [harvested_record],
        batch_source="youtube_data_api",
        batch_id=channel_id,
        via_temporal=via_temporal,
        workflow_prefix=workflow_prefix,
        task_queue=task_queue,
    )
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


async def _discover_youtube(
    *,
    keywords: str | None,
    niche: str | None,
    language: str | None,
    region: str | None,
    min_subscribers: int | None,
    max_subscribers: int | None,
    max_results_per_keyword: int,
    max_videos: int,
    via_temporal: bool,
    workflow_prefix: str,
    task_queue: str,
) -> None:
    """Discover channels by keywords, then route them into the canonical import path."""

    niche_config = get_niche_registry().get(niche) if niche else None
    parsed_keywords = [
        keyword.strip() for keyword in (keywords or "").split(",") if keyword.strip()
    ]
    if niche_config is not None and not parsed_keywords:
        parsed_keywords = niche_config.discovery.youtube_keywords
    if not parsed_keywords:
        raise typer.BadParameter("--keywords oder --niche ist fuer discover-youtube erforderlich.")

    effective_min_subscribers = (
        min_subscribers
        if min_subscribers is not None
        else niche_config.discovery.min_subscribers if niche_config is not None else None
    )
    effective_max_subscribers = (
        max_subscribers
        if max_subscribers is not None
        else niche_config.discovery.max_subscribers if niche_config is not None else None
    )
    languages = (
        [language]
        if language
        else (
            niche_config.discovery.languages
            if niche_config is not None and niche_config.discovery.languages
            else [None]
        )
    )
    regions = (
        [region]
        if region
        else (
            niche_config.discovery.regions
            if niche_config is not None and niche_config.discovery.regions
            else [None]
        )
    )

    harvester = YouTubeDataAPIHarvester()
    harvested_records = []
    seen_keys: set[str] = set()
    for language_value in languages:
        for region_value in regions:
            request = YouTubeKeywordDiscoveryRequest(
                keywords=parsed_keywords,
                language=language_value,
                region=region_value,
                min_subscribers=effective_min_subscribers,
                max_subscribers=effective_max_subscribers,
                max_results_per_keyword=max_results_per_keyword,
                max_videos=max_videos,
                source_labels=[
                    "youtube_keyword_discovery",
                    *([f"niche:{niche_config.niche_id}"] if niche_config is not None else []),
                ],
            )
            discovered = await harvester.discover_channels(request)
            for record in discovered:
                if niche_config is not None:
                    record.niche_labels = sorted(set([*record.niche_labels, niche_config.niche_id]))
                dedupe_key = record.external_id or f"{record.platform}:{record.handle}"
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                harvested_records.append(record)

    result = await CreatorSourceImportService().import_records(
        harvested_records,
        batch_source="youtube_search",
        batch_id=(
            niche_config.niche_id
            if niche_config is not None
            else "-".join(parsed_keywords[:3])
        ),
        via_temporal=via_temporal,
        workflow_prefix=workflow_prefix,
        task_queue=task_queue,
    )
    if niche_config is not None and result.results:
        async with get_session_factory()() as session:
            classifier_service = CreatorClassificationService(
                session=session,
                llm_providers=_build_llm_providers(),
                db_session_factory=get_session_factory(),
                langfuse_hook=LangfuseHook(),
            )
            for ingest_result in result.results:
                creator_id = UUID(ingest_result.creator_id)
                creator = await session.scalar(
                    select(Creator).where(Creator.id == creator_id)
                )
                if creator is None:
                    continue
                creator.niche_labels = sorted(set([*creator.niche_labels, niche_config.niche_id]))
                await classifier_service.classify_creator_by_handle(
                    platform=creator.platform,
                    handle=creator.handle,
                )
            await session.commit()
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


@brand_app.command("seed")
def seed_brands(
    file: Annotated[
        Path,
        typer.Option("--file", exists=True, readable=True),
    ],
) -> None:
    """Seed brands from a YAML file into the local database."""

    asyncio.run(_seed_brands(file))


async def _seed_brands(file: Path) -> None:
    """Import one brand seed file and print the summary."""

    async with get_session_factory()() as session:
        result = await BrandSeeder(session).seed_file(file)
        await session.commit()
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


@brand_app.command("enrich-websites")
def enrich_brand_websites(
    domain: str | None = typer.Option(None, "--domain"),
) -> None:
    """Fetch websites and derive creator-program/contact signals for brands."""

    asyncio.run(_enrich_brand_websites(domain=domain))


async def _enrich_brand_websites(domain: str | None) -> None:
    """Run website and search enrichment for one or all brands."""

    async with get_session_factory()() as session:
        brands = await _select_brands(session, domain=domain)
        enricher = BrandEnricher(session)
        results = [await enricher.enrich_brand(brand) for brand in brands]
        await session.commit()
    payload = [result.model_dump(mode="json") for result in results]
    typer.echo(
        json.dumps(payload, indent=2, ensure_ascii=False)
    )


@brand_app.command("score-spend-intent")
def score_brand_spend_intent(
    domain: str | None = typer.Option(None, "--domain"),
) -> None:
    """Compute the phase-1 spend-intent score for one or all brands."""

    asyncio.run(_score_brand_spend_intent(domain=domain))


async def _score_brand_spend_intent(domain: str | None) -> None:
    """Persist spend-intent scores for one or all brands."""

    scorer = BrandSpendIntentScorer()
    async with get_session_factory()() as session:
        brands = await _select_brands(session, domain=domain)
        results = [scorer.score_brand(brand) for brand in brands]
        await session.commit()
    payload = [result.model_dump(mode="json") for result in results]
    typer.echo(
        json.dumps(payload, indent=2, ensure_ascii=False)
    )


@brand_app.command("build-evidence")
def build_brand_evidence(
    domain: str | None = typer.Option(None, "--domain"),
) -> None:
    """Persist deterministic brand evidence items for one or all brands."""

    asyncio.run(_build_brand_evidence(domain=domain))


async def _build_brand_evidence(domain: str | None) -> None:
    """Build brand evidence from stored website and scoring signals."""

    async with get_session_factory()() as session:
        brands = await _select_brands(session, domain=domain)
        builder = EvidenceBuilderService(session=session)
        results = [await builder.build_brand_evidence(brand_id=brand.id) for brand in brands]
        await session.commit()
    payload = [result.model_dump(mode="json") for result in results]
    typer.echo(
        json.dumps(payload, indent=2, ensure_ascii=False)
    )


async def _select_brands(session, *, domain: str | None) -> list[Brand]:
    """Load one brand by domain or all brands when no filter is provided."""

    service = BrandService(session)
    if domain is not None:
        brand = await service.get_by_domain(domain)
        if brand is None:
            raise typer.BadParameter(f"Brand mit Domain {domain} wurde nicht gefunden.")
        return [brand]
    return await service.list_brands()


@evidence_app.command("build-creator")
def build_creator_evidence(
    handle: str = typer.Option(..., "--handle"),
    platform: str = typer.Option(..., "--platform"),
) -> None:
    """Build evidence artifacts and evidence_items for one creator."""

    asyncio.run(_build_creator_evidence(handle=handle, platform=platform))


async def _build_creator_evidence(handle: str, platform: str) -> None:
    """Execute the local evidence builder for one creator handle."""

    executor = AgentExecutor(
        contract=EVIDENCE_BUILDER_CONTRACT,
        llm_providers=_build_llm_providers(),
        db_session_factory=get_session_factory(),
        langfuse_hook=LangfuseHook(),
    )
    async with get_session_factory()() as session:
        service = EvidenceBuilderService(session, agent_executor=executor)
        result = await service.build_creator_evidence_by_handle(platform=platform, handle=handle)
        await session.commit()
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=True))


@temporal_app.command("run-creator-worker")
def run_creator_worker_command(
    task_queue: str = typer.Option(CREATOR_TASK_QUEUE, "--task-queue"),
) -> None:
    """Run the local Temporal worker for creator ingest workflows."""

    asyncio.run(run_creator_worker(task_queue=task_queue))


@temporal_app.command("ingest-creator")
def ingest_creator_workflow(
    input_file: Annotated[
        Path,
        typer.Option("--input-file", exists=True, readable=True),
    ],
    workflow_id: str | None = typer.Option(None, "--workflow-id"),
    task_queue: str = typer.Option(CREATOR_TASK_QUEUE, "--task-queue"),
) -> None:
    """Execute the creator ingest workflow on the local Temporal server."""

    asyncio.run(
        _execute_creator_ingest_workflow(
            input_file=input_file,
            workflow_id=workflow_id,
            task_queue=task_queue,
        )
    )


async def _execute_creator_ingest_workflow(
    input_file: Path,
    workflow_id: str | None,
    task_queue: str,
) -> None:
    """Start one creator ingest workflow and print the structured result."""

    payload = CreatorIngestInput.model_validate_json(input_file.read_text(encoding="utf-8"))
    client = await get_temporal_client()
    result = await client.execute_workflow(
        CREATOR_INGEST_WORKFLOW,
        payload,
        id=workflow_id or f"creator-ingest-{payload.platform}-{payload.handle}",
        task_queue=task_queue,
        result_type=CreatorIngestResult,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
