"""Tests for creator ingest and upsert behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from ima.creators.ingest import (
    CreatorContentInput,
    CreatorIngestInput,
    CreatorIngestService,
    CreatorMetricSnapshotPayload,
)
from ima.db.models import Creator, CreatorContent, CreatorMetricSnapshot


async def test_creator_ingest_creates_records_and_scores(sqlite_session_factory) -> None:
    """A fresh ingest payload should create creator, content, snapshot, and score."""

    async with sqlite_session_factory() as session:
        service = CreatorIngestService(session)
        result = await service.ingest(
            CreatorIngestInput(
                platform="youtube",
                handle="ingestfresh",
                external_id="yt-ingestfresh",
                profile_url="https://youtube.com/@ingestfresh",
                display_name="Ingest Fresh",
                bio="Hyrox coach and nutrition creator from Vienna.",
                followers=180000,
                language="en",
                niche_labels=["fitness", "hyrox", "nutrition"],
                source_labels=["youtube_api"],
                metric_snapshot=CreatorMetricSnapshotPayload(
                    captured_at=datetime.now(UTC),
                    followers=180000,
                    average_views_30d=18000,
                    engagement_rate_30d=Decimal("0.0450"),
                    source="fixture",
                ),
                content_items=[
                    CreatorContentInput(
                        platform_content_id="video-1",
                        content_type="video",
                        url="https://youtube.com/watch?v=video-1",
                        title="Training Breakdown",
                        caption="Training and nutrition breakdown.",
                        hashtags=["hyrox", "fitness", "vienna"],
                        raw_payload={"source": "fixture"},
                    ),
                    CreatorContentInput(
                        platform_content_id="video-2",
                        content_type="video",
                        url="https://youtube.com/watch?v=video-2",
                        title="Race Prep",
                        caption="Race prep for the next Hyrox event.",
                        hashtags=["hyrox", "race", "nutrition"],
                        raw_payload={"source": "fixture"},
                    ),
                    CreatorContentInput(
                        platform_content_id="video-3",
                        content_type="video",
                        url="https://youtube.com/watch?v=video-3",
                        title="Nutrition Week",
                        caption="What I eat in race week.",
                        hashtags=["nutrition", "fitness", "food"],
                        raw_payload={"source": "fixture"},
                    ),
                ],
            )
        )
        await session.commit()

        creator_count = await session.scalar(select(func.count()).select_from(Creator))
        content_count = await session.scalar(select(func.count()).select_from(CreatorContent))
        snapshot_count = await session.scalar(
            select(func.count()).select_from(CreatorMetricSnapshot)
        )

    assert result.created is True
    assert result.content_created == 3
    assert result.content_updated == 0
    assert result.snapshot_recorded is True
    assert result.score.commercial_score >= 0.6
    assert result.score.niche_fit_score >= 0.5
    assert creator_count == 1
    assert content_count == 3
    assert snapshot_count == 1


async def test_creator_ingest_updates_existing_creator_content(sqlite_session_factory) -> None:
    """A repeated ingest should update matched content instead of duplicating it."""

    async with sqlite_session_factory() as session:
        service = CreatorIngestService(session)
        first = await service.ingest(
            CreatorIngestInput(
                platform="youtube",
                handle="ingestupdate",
                profile_url="https://youtube.com/@ingestupdate",
                bio="Fitness creator",
                followers=120000,
                niche_labels=["fitness"],
                source_labels=["seed_a"],
                metric_snapshot=CreatorMetricSnapshotPayload(
                    captured_at=datetime.now(UTC) - timedelta(days=30),
                    followers=100000,
                    average_views_30d=9000,
                    source="fixture",
                ),
                content_items=[
                    CreatorContentInput(
                        platform_content_id="video-1",
                        content_type="video",
                        url="https://youtube.com/watch?v=video-1",
                        title="Old title",
                        caption="First payload",
                        hashtags=["fitness"],
                        raw_payload={"version": 1},
                    )
                ],
            )
        )
        second = await service.ingest(
            CreatorIngestInput(
                platform="youtube",
                handle="ingestupdate",
                display_name="Updated Name",
                bio="Updated fitness creator bio",
                followers=135000,
                niche_labels=["fitness", "hyrox"],
                source_labels=["seed_b"],
                metric_snapshot=CreatorMetricSnapshotPayload(
                    captured_at=datetime.now(UTC),
                    followers=135000,
                    average_views_30d=14000,
                    source="fixture",
                ),
                content_items=[
                    CreatorContentInput(
                        platform_content_id="video-1",
                        content_type="video",
                        url="https://youtube.com/watch?v=video-1",
                        title="New title",
                        caption="Updated payload",
                        hashtags=["fitness", "hyrox"],
                        raw_payload={"version": 2},
                    )
                ],
            )
        )
        await session.commit()

        creator = await session.scalar(select(Creator).where(Creator.handle == "ingestupdate"))
        content_rows = list((await session.scalars(select(CreatorContent))).all())
        snapshot_count = await session.scalar(
            select(func.count()).select_from(CreatorMetricSnapshot)
        )

    assert first.created is True
    assert second.created is False
    assert second.content_created == 0
    assert second.content_updated == 1
    assert creator is not None
    assert creator.display_name == "Updated Name"
    assert creator.source_labels == ["seed_a", "seed_b"]
    assert len(content_rows) == 1
    assert content_rows[0].title == "New title"
    assert snapshot_count == 2
