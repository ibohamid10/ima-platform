"""Creator ingest service that upserts creators, content, and growth snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
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
        creator.followers = payload.followers or creator.followers
        creator.language = payload.language or creator.language
        creator.geo = payload.geo or creator.geo
        creator.niche_labels = sorted(set([*creator.niche_labels, *payload.niche_labels]))
        creator.email = payload.email or creator.email
        creator.email_confidence = (
            Decimal(str(payload.email_confidence))
            if payload.email_confidence is not None
            else creator.email_confidence
        )
        creator.consent_basis = payload.consent_basis
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
            content_record.caption = content_payload.caption
            content_record.published_at = content_payload.published_at
            content_record.view_count = content_payload.view_count
            content_record.like_count = content_payload.like_count
            content_record.comment_count = content_payload.comment_count
            content_record.hashtags = content_payload.hashtags
            content_record.detected_brands = content_payload.detected_brands
            content_record.sponsor_probability = (
                Decimal(str(content_payload.sponsor_probability))
                if content_payload.sponsor_probability is not None
                else None
            )
            content_record.raw_snapshot_uri = content_payload.raw_snapshot_uri
            content_record.raw_payload = content_payload.raw_payload

        snapshot_recorded = False
        if payload.metric_snapshot is not None:
            await self.scoring_service.record_snapshot(
                CreatorGrowthSnapshotInput(
                    creator_id=str(creator.id),
                    captured_at=payload.metric_snapshot.captured_at,
                    followers=(
                        payload.metric_snapshot.followers
                        if payload.metric_snapshot.followers is not None
                        else payload.followers
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
