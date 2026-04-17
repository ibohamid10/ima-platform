"""Tests for evidence building, storage, and evidence item persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from ima.agents.evidence_builder.contract import EvidenceBuilderOutput
from ima.creators.ingest import CreatorContentInput, CreatorIngestInput, CreatorIngestService
from ima.creators.schemas import CreatorMetricSnapshotPayload
from ima.db.models import EvidenceItem
from ima.evidence.builder import EvidenceBuilderService
from ima.evidence.storage import LocalEvidenceStorage


class FakeEvidencePageFetcher:
    """Deterministic HTML fetcher for evidence builder tests."""

    async def fetch_html(self, url: str) -> str:
        """Return predictable HTML content for the requested URL."""

        return f"<html><body>{url}</body></html>"


class FakeEvidenceVisualFetcher:
    """Deterministic PNG fetcher for evidence screenshot tests."""

    async def capture_png(self, url: str) -> bytes:
        """Return predictable PNG-like bytes for the requested URL."""

        return f"png:{url}".encode()


class FakeEvidenceAgentExecutor:
    """Deterministic evidence-agent stub for builder-service unit tests."""

    async def run(self, inputs) -> EvidenceBuilderOutput:
        """Return stable evidence items based on the incoming content records."""

        items = []
        if inputs.bio:
            items.append(
                {
                    "claim_text": inputs.bio,
                    "source_uri": "bio",
                    "source_type": "bio",
                    "confidence": 0.75,
                }
            )
        for record in inputs.recent_content:
            items.append(
                {
                    "claim_text": record.title or record.caption or "Recent content observed.",
                    "source_uri": record.source_uri,
                    "source_type": record.source_type,
                    "confidence": 0.7,
                }
            )
        return EvidenceBuilderOutput(evidence_items=items)


async def test_evidence_builder_persists_items_and_artifacts(
    sqlite_session_factory,
    tmp_path: Path,
) -> None:
    """A creator with content and metrics should produce evidence rows and artifacts."""

    async with sqlite_session_factory() as session:
        ingest_service = CreatorIngestService(session)
        await ingest_service.ingest(
            CreatorIngestInput(
                platform="youtube",
                handle="evidencefresh",
                external_id="yt-evidencefresh",
                profile_url="https://youtube.com/@evidencefresh",
                display_name="Evidence Fresh",
                bio="Hyrox coach and nutrition creator from Vienna.",
                followers=180000,
                language="en",
                niche_labels=["fitness", "hyrox", "nutrition"],
                source_labels=["youtube_api"],
                metric_snapshot=CreatorMetricSnapshotPayload(
                    captured_at=datetime.now(UTC),
                    followers=180000,
                    average_views_30d=18000,
                    average_likes_30d=1200,
                    average_comments_30d=90,
                    engagement_rate_30d=Decimal("0.0450"),
                    source="fixture",
                ),
                content_items=[
                    CreatorContentInput(
                        platform_content_id="video-11",
                        content_type="video",
                        url="https://youtube.com/watch?v=video-11",
                        title="Training Breakdown",
                        caption="Training and nutrition breakdown.",
                        hashtags=["hyrox", "fitness", "vienna"],
                        raw_payload={"source": "fixture"},
                    ),
                    CreatorContentInput(
                        platform_content_id="video-12",
                        content_type="video",
                        url="https://youtube.com/watch?v=video-12",
                        title="Race Prep",
                        caption="Race prep for the next Hyrox event.",
                        hashtags=["hyrox", "race", "nutrition"],
                        raw_payload={"source": "fixture"},
                    ),
                ],
            )
        )
        await session.commit()

    evidence_root = tmp_path / "evidence-store"
    async with sqlite_session_factory() as session:
        builder = EvidenceBuilderService(
            session,
            storage=LocalEvidenceStorage(root=evidence_root, bucket="test-evidence"),
            page_fetcher=FakeEvidencePageFetcher(),
            visual_fetcher=FakeEvidenceVisualFetcher(),
            agent_executor=FakeEvidenceAgentExecutor(),
        )
        result = await builder.build_creator_evidence_by_handle(
            platform="youtube",
            handle="evidencefresh",
        )
        await session.commit()
        evidence_count = await session.scalar(select(func.count()).select_from(EvidenceItem))
        stored_items = list((await session.scalars(select(EvidenceItem))).all())

    assert result.evidence_count == 3
    assert result.artifact_count == 10
    assert evidence_count == 3
    assert all(item.source_uri for item in stored_items)
    assert all(item.confidence is not None for item in stored_items)
    assert (
        evidence_root / "creators" / "youtube" / "evidencefresh" / "profile" / "current.json"
    ).exists()
    assert (
        evidence_root / "creators" / "youtube" / "evidencefresh" / "profile" / "page.html"
    ).exists()
    assert (
        evidence_root / "creators" / "youtube" / "evidencefresh" / "profile" / "page.png"
    ).exists()
    assert result.artifact_uris[0].startswith("evidence://test-evidence/")


async def test_evidence_builder_is_idempotent_on_source_keys(
    sqlite_session_factory,
    tmp_path: Path,
) -> None:
    """Rebuilding evidence should update stable source keys instead of duplicating rows."""

    async with sqlite_session_factory() as session:
        ingest_service = CreatorIngestService(session)
        await ingest_service.ingest(
            CreatorIngestInput(
                platform="youtube",
                handle="evidenceupdate",
                profile_url="https://youtube.com/@evidenceupdate",
                bio="Fitness creator with repeatable evidence.",
                followers=140000,
                niche_labels=["fitness"],
                source_labels=["fixture"],
                metric_snapshot=CreatorMetricSnapshotPayload(
                    captured_at=datetime.now(UTC),
                    followers=140000,
                    average_views_30d=12000,
                    source="fixture",
                ),
                content_items=[
                    CreatorContentInput(
                        platform_content_id="video-21",
                        content_type="video",
                        url="https://youtube.com/watch?v=video-21",
                        title="First title",
                        caption="First caption",
                        raw_payload={"version": 1},
                    )
                ],
            )
        )
        await session.commit()

    storage = LocalEvidenceStorage(root=tmp_path / "evidence-store", bucket="test-evidence")
    async with sqlite_session_factory() as session:
        builder = EvidenceBuilderService(
            session,
            storage=storage,
            page_fetcher=FakeEvidencePageFetcher(),
            visual_fetcher=FakeEvidenceVisualFetcher(),
            agent_executor=FakeEvidenceAgentExecutor(),
        )
        first = await builder.build_creator_evidence_by_handle(
            platform="youtube", handle="evidenceupdate"
        )
        second = await builder.build_creator_evidence_by_handle(
            platform="youtube", handle="evidenceupdate"
        )
        await session.commit()
        evidence_count = await session.scalar(select(func.count()).select_from(EvidenceItem))

    assert first.evidence_count == second.evidence_count
    assert evidence_count == first.evidence_count
