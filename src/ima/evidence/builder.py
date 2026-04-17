"""Evidence builder for creator profiles and content-based claim coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ima.db.models import Creator, CreatorContent, CreatorMetricSnapshot, EvidenceItem
from ima.evidence.schemas import EvidenceBuildResult, EvidenceItemResult
from ima.evidence.storage import EvidenceStorage, LocalEvidenceStorage
from ima.logging import get_logger

logger = get_logger(__name__)


class EvidenceBuilderService:
    """Build evidence artifacts and evidence_items from canonical creator data."""

    def __init__(
        self,
        session: AsyncSession,
        storage: EvidenceStorage | None = None,
    ) -> None:
        """Create the evidence builder for one async session."""

        self.session = session
        self.storage = storage or LocalEvidenceStorage()

    async def build_creator_evidence_by_handle(
        self,
        *,
        platform: str,
        handle: str,
    ) -> EvidenceBuildResult:
        """Resolve a creator by platform and handle before building evidence."""

        creator = await self.session.scalar(
            select(Creator).where(Creator.platform == platform, Creator.handle == handle)
        )
        if creator is None:
            raise ValueError(f"Creator {platform}/{handle} wurde nicht gefunden.")
        return await self.build_creator_evidence(creator_id=creator.id)

    async def build_creator_evidence(self, *, creator_id: UUID) -> EvidenceBuildResult:
        """Build evidence artifacts and structured evidence items for one creator."""

        creator = await self.session.get(Creator, creator_id)
        if creator is None:
            raise ValueError(f"Creator {creator_id} wurde nicht gefunden.")

        content_items = list(
            (
                await self.session.scalars(
                    select(CreatorContent)
                    .where(CreatorContent.creator_id == creator_id)
                    .order_by(CreatorContent.published_at.desc().nullslast())
                )
            ).all()
        )
        latest_snapshot = await self.session.scalar(
            select(CreatorMetricSnapshot)
            .where(CreatorMetricSnapshot.creator_id == creator_id)
            .order_by(CreatorMetricSnapshot.captured_at.desc())
        )

        artifact_uris: list[str] = []
        evidence_results: list[EvidenceItemResult] = []

        profile_artifact = await self.storage.put_json(
            key=self._artifact_key(
                creator=creator,
                suffix="profile/current.json",
            ),
            payload={
                "creator_id": str(creator.id),
                "platform": creator.platform,
                "handle": creator.handle,
                "profile_url": creator.profile_url,
                "display_name": creator.display_name,
                "bio": creator.bio,
                "follower_count": creator.follower_count,
                "primary_language": creator.primary_language,
                "niche": creator.niche,
                "sub_niches": creator.sub_niches,
                "source_labels": creator.source_labels,
                "built_at": datetime.now(UTC).isoformat(),
            },
        )
        artifact_uris.append(profile_artifact.source_uri)

        if creator.bio:
            evidence_results.append(
                await self._upsert_evidence_item(
                    creator_id=creator.id,
                    source_key=f"creator:{creator.id}:bio",
                    evidence_type="creator_bio",
                    source_kind="creator_profile",
                    claim_text=creator.bio,
                    source_uri=profile_artifact.source_uri,
                    artifact_uri=profile_artifact.source_uri,
                    snippet_text=creator.bio,
                    metadata_json={
                        "platform": creator.platform,
                        "handle": creator.handle,
                    },
                )
            )

        if creator.follower_count is not None:
            evidence_results.append(
                await self._upsert_evidence_item(
                    creator_id=creator.id,
                    source_key=f"creator:{creator.id}:follower_count",
                    evidence_type="creator_metric",
                    source_kind="creator_profile",
                    claim_text=f"Follower count observed at {creator.follower_count}.",
                    source_uri=profile_artifact.source_uri,
                    artifact_uri=profile_artifact.source_uri,
                    snippet_text=str(creator.follower_count),
                    metadata_json={
                        "metric_name": "follower_count",
                        "metric_value": creator.follower_count,
                    },
                )
            )

        if latest_snapshot is not None:
            snapshot_artifact = await self.storage.put_json(
                key=self._artifact_key(
                    creator=creator,
                    suffix="metrics/latest.json",
                ),
                payload={
                    "snapshot_id": str(latest_snapshot.id),
                    "creator_id": str(creator.id),
                    "captured_at": latest_snapshot.captured_at.isoformat(),
                    "follower_count": latest_snapshot.follower_count,
                    "average_views_30d": latest_snapshot.average_views_30d,
                    "average_likes_30d": latest_snapshot.average_likes_30d,
                    "average_comments_30d": latest_snapshot.average_comments_30d,
                    "engagement_rate_30d": (
                        str(latest_snapshot.engagement_rate_30d)
                        if latest_snapshot.engagement_rate_30d is not None
                        else None
                    ),
                    "source": latest_snapshot.source,
                },
            )
            artifact_uris.append(snapshot_artifact.source_uri)
            if latest_snapshot.average_views_30d is not None:
                evidence_results.append(
                    await self._upsert_evidence_item(
                        creator_id=creator.id,
                        snapshot_id=latest_snapshot.id,
                        source_key=f"snapshot:{latest_snapshot.id}:average_views_30d",
                        evidence_type="creator_metric",
                        source_kind="creator_snapshot",
                        claim_text=(
                            f"Average views over recent sampled videos observed at "
                            f"{latest_snapshot.average_views_30d}."
                        ),
                        source_uri=snapshot_artifact.source_uri,
                        artifact_uri=snapshot_artifact.source_uri,
                        snippet_text=str(latest_snapshot.average_views_30d),
                        metadata_json={
                            "metric_name": "average_views_30d",
                            "metric_value": latest_snapshot.average_views_30d,
                        },
                    )
                )

        for content in content_items:
            content_artifact = await self.storage.put_json(
                key=self._artifact_key(
                    creator=creator,
                    suffix=f"content/{self._content_key(content)}/raw.json",
                ),
                payload={
                    "content_id": str(content.id),
                    "creator_id": str(creator.id),
                    "platform_content_id": content.platform_content_id,
                    "content_type": content.content_type,
                    "url": content.url,
                    "title": content.title,
                    "caption_text": content.caption_text,
                    "published_at": (
                        content.published_at.isoformat()
                        if content.published_at is not None
                        else None
                    ),
                    "view_count": content.view_count,
                    "like_count": content.like_count,
                    "comment_count": content.comment_count,
                    "top_hashtags": content.top_hashtags,
                    "raw_payload": content.raw_payload,
                },
            )
            artifact_uris.append(content_artifact.source_uri)

            if content.title:
                evidence_results.append(
                    await self._upsert_evidence_item(
                        creator_id=creator.id,
                        content_id=content.id,
                        source_key=f"content:{content.id}:title",
                        evidence_type="content_title",
                        source_kind="creator_content",
                        claim_text=content.title,
                        source_uri=content.url or content_artifact.source_uri,
                        artifact_uri=content_artifact.source_uri,
                        snippet_text=content.title,
                        metadata_json={
                            "platform_content_id": content.platform_content_id,
                            "content_type": content.content_type,
                        },
                    )
                )

            if content.caption_text:
                evidence_results.append(
                    await self._upsert_evidence_item(
                        creator_id=creator.id,
                        content_id=content.id,
                        source_key=f"content:{content.id}:caption",
                        evidence_type="content_caption",
                        source_kind="creator_content",
                        claim_text=content.caption_text,
                        source_uri=content.url or content_artifact.source_uri,
                        artifact_uri=content_artifact.source_uri,
                        snippet_text=content.caption_text,
                        metadata_json={
                            "platform_content_id": content.platform_content_id,
                            "content_type": content.content_type,
                        },
                    )
                )

        await self.session.flush()
        logger.info(
            "creator_evidence_built",
            creator_id=str(creator.id),
            handle=creator.handle,
            platform=creator.platform,
            evidence_count=len(evidence_results),
            artifact_count=len(artifact_uris),
        )
        return EvidenceBuildResult(
            creator_id=str(creator.id),
            platform=creator.platform,
            handle=creator.handle,
            evidence_count=len(evidence_results),
            artifact_count=len(artifact_uris),
            artifact_uris=artifact_uris,
            evidence_items=evidence_results,
        )

    async def _upsert_evidence_item(
        self,
        *,
        creator_id: UUID,
        source_key: str,
        evidence_type: str,
        source_kind: str,
        claim_text: str,
        source_uri: str,
        artifact_uri: str | None,
        snippet_text: str | None,
        metadata_json: dict[str, object],
        content_id: UUID | None = None,
        snapshot_id: UUID | None = None,
    ) -> EvidenceItemResult:
        """Insert or update one evidence item under a stable source key."""

        evidence_item = await self.session.scalar(
            select(EvidenceItem).where(EvidenceItem.source_key == source_key)
        )
        if evidence_item is None:
            evidence_item = EvidenceItem(
                creator_id=creator_id,
                content_id=content_id,
                snapshot_id=snapshot_id,
                source_key=source_key,
                evidence_type=evidence_type,
                source_kind=source_kind,
                claim_text=claim_text,
                source_uri=source_uri,
                artifact_uri=artifact_uri,
                snippet_text=snippet_text,
                metadata_json=metadata_json,
            )
            self.session.add(evidence_item)
        else:
            evidence_item.creator_id = creator_id
            evidence_item.content_id = content_id
            evidence_item.snapshot_id = snapshot_id
            evidence_item.evidence_type = evidence_type
            evidence_item.source_kind = source_kind
            evidence_item.claim_text = claim_text
            evidence_item.source_uri = source_uri
            evidence_item.artifact_uri = artifact_uri
            evidence_item.snippet_text = snippet_text
            evidence_item.metadata_json = metadata_json

        await self.session.flush()
        return EvidenceItemResult(
            evidence_id=str(evidence_item.id),
            source_key=evidence_item.source_key,
            evidence_type=evidence_item.evidence_type,
            claim_text=evidence_item.claim_text,
            source_uri=evidence_item.source_uri,
            artifact_uri=evidence_item.artifact_uri,
            snippet_text=evidence_item.snippet_text,
        )

    def _artifact_key(self, *, creator: Creator, suffix: str) -> str:
        """Build a stable evidence storage key for one creator-scoped artifact."""

        return f"creators/{creator.platform}/{creator.handle}/{suffix}"

    def _content_key(self, content: CreatorContent) -> str:
        """Resolve a stable content artifact key segment."""

        return content.platform_content_id or str(content.id)
