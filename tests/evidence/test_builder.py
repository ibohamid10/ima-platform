"""Tests for evidence building, storage, and evidence item persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

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
                follower_count=180000,
                primary_language="en",
                source_labels=["youtube_api"],
                metric_snapshot=CreatorMetricSnapshotPayload(
                    captured_at=datetime.now(UTC),
                    follower_count=180000,
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
                        caption_text="Training and nutrition breakdown.",
                        top_hashtags=["hyrox", "fitness", "vienna"],
                        raw_payload={"source": "fixture"},
                    ),
                    CreatorContentInput(
                        platform_content_id="video-12",
                        content_type="video",
                        url="https://youtube.com/watch?v=video-12",
                        title="Race Prep",
                        caption_text="Race prep for the next Hyrox event.",
                        top_hashtags=["hyrox", "race", "nutrition"],
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
        )
        result = await builder.build_creator_evidence_by_handle(
            platform="youtube",
            handle="evidencefresh",
        )
        await session.commit()
        evidence_count = await session.scalar(select(func.count()).select_from(EvidenceItem))
        stored_items = list((await session.scalars(select(EvidenceItem))).all())

    assert result.evidence_count == 7
    assert result.artifact_count == 7
    assert evidence_count == 7
    assert all(item.source_uri for item in stored_items)
    assert (evidence_root / "creators" / "youtube" / "evidencefresh" / "profile" / "current.json").exists()
    assert (evidence_root / "creators" / "youtube" / "evidencefresh" / "profile" / "page.html").exists()
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
                follower_count=140000,
                source_labels=["fixture"],
                metric_snapshot=CreatorMetricSnapshotPayload(
                    captured_at=datetime.now(UTC),
                    follower_count=140000,
                    average_views_30d=12000,
                    source="fixture",
                ),
                content_items=[
                    CreatorContentInput(
                        platform_content_id="video-21",
                        content_type="video",
                        url="https://youtube.com/watch?v=video-21",
                        title="First title",
                        caption_text="First caption",
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
        )
        first = await builder.build_creator_evidence_by_handle(platform="youtube", handle="evidenceupdate")
        second = await builder.build_creator_evidence_by_handle(platform="youtube", handle="evidenceupdate")
        await session.commit()
        evidence_count = await session.scalar(select(func.count()).select_from(EvidenceItem))

    assert first.evidence_count == second.evidence_count
    assert evidence_count == first.evidence_count
