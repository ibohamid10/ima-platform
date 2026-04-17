"""Creator ingest service that upserts creators, content, and growth snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ima.creators.schemas import (
    CreatorContentInput,
    CreatorGrowthSnapshotInput,
    CreatorIngestInput,
    CreatorIngestResult,
    CreatorMetricSnapshotPayload,
)
from ima.creators.scoring import CreatorScoringService
from ima.db.models import Creator, CreatorContent
from ima.logging import get_logger

logger = get_logger(__name__)
__all__ = [
    "CreatorContentInput",
    "CreatorIngestInput",
    "CreatorIngestResult",
    "CreatorIngestService",
    "CreatorMetricSnapshotPayload",
]


class CreatorIngestService:
    """Service that ingests creator source data and triggers first scoring."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a creator ingest service for one async session."""

        self.session = session
        self.scoring_service = CreatorScoringService(session)

    async def ingest(self, payload: CreatorIngestInput) -> CreatorIngestResult:
        """Upsert a creator, related content, an optional snapshot, and refreshed score."""

        creator = await self.session.scalar(
            select(Creator).where(
                Creator.platform == payload.platform,
                Creator.handle == payload.handle,
            )
        )
        created = creator is None
        if creator is None:
            creator = Creator(
                platform=payload.platform,
                handle=payload.handle,
            )
            self.session.add(creator)
            await self.session.flush()

        creator.external_id = payload.external_id or creator.external_id
        creator.profile_url = payload.profile_url or creator.profile_url
        creator.display_name = payload.display_name or creator.display_name
        creator.bio = payload.bio or creator.bio
        creator.follower_count = payload.follower_count or creator.follower_count
        creator.primary_language = payload.primary_language or creator.primary_language
        creator.niche = payload.niche or creator.niche
        creator.sub_niches = payload.sub_niches or creator.sub_niches
        creator.consent_status = payload.consent_status
        creator.source_labels = sorted(set([*creator.source_labels, *payload.source_labels]))
        creator.last_seen_at = datetime.now(UTC)

        content_created = 0
        content_updated = 0
        for content_payload in payload.content_items:
            content_record = await self._find_existing_content(
                creator_id=creator.id,
                payload=content_payload,
            )
            if content_record is None:
                content_record = CreatorContent(
                    creator_id=creator.id,
                    platform_content_id=content_payload.platform_content_id,
                    content_type=content_payload.content_type,
                )
                self.session.add(content_record)
                content_created += 1
            else:
                content_updated += 1

            content_record.url = content_payload.url
            content_record.title = content_payload.title
            content_record.caption_text = content_payload.caption_text
            content_record.published_at = content_payload.published_at
            content_record.view_count = content_payload.view_count
            content_record.like_count = content_payload.like_count
            content_record.comment_count = content_payload.comment_count
            content_record.top_hashtags = content_payload.top_hashtags
            content_record.raw_payload = content_payload.raw_payload

        snapshot_recorded = False
        if payload.metric_snapshot is not None:
            await self.scoring_service.record_snapshot(
                CreatorGrowthSnapshotInput(
                    creator_id=str(creator.id),
                    captured_at=payload.metric_snapshot.captured_at,
                    follower_count=(
                        payload.metric_snapshot.follower_count
                        if payload.metric_snapshot.follower_count is not None
                        else payload.follower_count
                    ),
                    average_views_30d=payload.metric_snapshot.average_views_30d,
                    average_likes_30d=payload.metric_snapshot.average_likes_30d,
                    average_comments_30d=payload.metric_snapshot.average_comments_30d,
                    engagement_rate_30d=payload.metric_snapshot.engagement_rate_30d,
                    source=payload.metric_snapshot.source,
                )
            )
            snapshot_recorded = True

        score = await self.scoring_service.score_creator(str(creator.id))
        await self.session.flush()

        logger.info(
            "creator_ingested",
            creator_id=str(creator.id),
            created=created,
            content_created=content_created,
            content_updated=content_updated,
            snapshot_recorded=snapshot_recorded,
        )

        return CreatorIngestResult(
            creator_id=str(creator.id),
            created=created,
            content_created=content_created,
            content_updated=content_updated,
            snapshot_recorded=snapshot_recorded,
            score=score,
        )

    async def _find_existing_content(
        self,
        creator_id: UUID,
        payload: CreatorContentInput,
    ) -> CreatorContent | None:
        """Find an existing content row for idempotent ingest updates."""

        if payload.platform_content_id is not None:
            return await self.session.scalar(
                select(CreatorContent).where(
                    CreatorContent.creator_id == creator_id,
                    CreatorContent.platform_content_id == payload.platform_content_id,
                )
            )

        if payload.url is not None:
            return await self.session.scalar(
                select(CreatorContent).where(
                    CreatorContent.creator_id == creator_id,
                    CreatorContent.url == payload.url,
                )
            )
        return None
