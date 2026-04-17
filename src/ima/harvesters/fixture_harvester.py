"""Fixture-based harvester and enricher stubs for local creator source imports."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ima.creators.schemas import (
    CreatorContentInput,
    CreatorIngestInput,
    CreatorMetricSnapshotPayload,
)
from ima.harvesters.schemas import HarvestedCreatorRecord, HarvestFixtureBatch


class FixtureCreatorHarvester:
    """Load creator source fixtures from disk for local pipeline development."""

    async def harvest_from_file(self, input_file: Path) -> HarvestFixtureBatch:
        """Load one local fixture batch into structured harvested records."""

        payload = await asyncio.to_thread(input_file.read_text, encoding="utf-8")
        return HarvestFixtureBatch.model_validate_json(payload)


class CreatorEnricherStub:
    """Normalize harvested creator records into the canonical ingest contract."""

    async def enrich(self, record: HarvestedCreatorRecord) -> CreatorIngestInput:
        """Convert one harvested record into the shared creator ingest payload."""

        source_labels = sorted(
            set(
                [
                    *record.source_labels,
                    f"harvester:{record.source}",
                    "enricher:stub",
                ]
            )
        )
        metric_snapshot = None
        if record.metric_snapshot is not None:
            metric_snapshot = CreatorMetricSnapshotPayload(
                captured_at=record.metric_snapshot.captured_at,
                followers=record.metric_snapshot.followers,
                average_views_30d=record.metric_snapshot.average_views_30d,
                average_likes_30d=record.metric_snapshot.average_likes_30d,
                average_comments_30d=record.metric_snapshot.average_comments_30d,
                engagement_rate_30d=record.metric_snapshot.engagement_rate_30d,
                source=record.metric_snapshot.source,
            )

        return CreatorIngestInput(
            platform=record.platform,
            handle=record.handle,
            external_id=record.external_id,
            profile_url=record.profile_url,
            display_name=record.display_name,
            bio=record.bio,
            followers=record.followers,
            language=record.language,
            geo=record.geo,
            niche_labels=record.niche_labels,
            email=record.email,
            email_confidence=record.email_confidence,
            source_labels=source_labels,
            metric_snapshot=metric_snapshot,
            content_items=[
                CreatorContentInput(
                    platform_content_id=item.platform_content_id,
                    content_type=item.content_type,
                    url=item.url,
                    title=item.title,
                    caption=item.caption,
                    published_at=item.published_at,
                    view_count=item.view_count,
                    like_count=item.like_count,
                    comment_count=item.comment_count,
                    hashtags=item.hashtags,
                    detected_brands=item.detected_brands,
                    sponsor_probability=item.sponsor_probability,
                    raw_snapshot_uri=item.raw_snapshot_uri,
                    raw_payload=item.raw_payload,
                )
                for item in record.content_items
            ],
        )
