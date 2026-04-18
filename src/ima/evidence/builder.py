"""Evidence builder that prepares artifacts and persists agent-generated evidence."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ima.agents.evidence_builder.contract import (
    EvidenceBuilderInput,
    EvidenceBuilderOutput,
    EvidenceContentRecord,
)
from ima.agents.executor import AgentExecutor
from ima.db.models import Brand, Creator, CreatorContent, CreatorMetricSnapshot, EvidenceItem
from ima.evidence.fetchers import (
    EvidencePageFetcher,
    EvidenceVisualFetcher,
    HttpEvidencePageFetcher,
    PlaywrightScreenshotFetcher,
)
from ima.evidence.schemas import BrandEvidenceBuildResult, EvidenceBuildResult, EvidenceItemResult
from ima.evidence.storage import EvidenceStorage, LocalEvidenceStorage
from ima.logging import get_logger

logger = get_logger(__name__)


class EvidenceBuilderService:
    """Prepare artifacts, execute the evidence agent, and persist evidence items."""

    def __init__(
        self,
        session: AsyncSession,
        storage: EvidenceStorage | None = None,
        page_fetcher: EvidencePageFetcher | None = None,
        visual_fetcher: EvidenceVisualFetcher | None = None,
        agent_executor: AgentExecutor | None = None,
    ) -> None:
        """Create the evidence builder for one async session."""

        self.session = session
        self.storage = storage or LocalEvidenceStorage()
        self.page_fetcher = page_fetcher or HttpEvidencePageFetcher()
        self.visual_fetcher = visual_fetcher or PlaywrightScreenshotFetcher()
        self.agent_executor = agent_executor

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
        """Build artifacts, run the evidence agent, and persist one creator's evidence items."""

        if self.agent_executor is None:
            raise ValueError(
                "EvidenceBuilderService braucht einen AgentExecutor fuer Evidence-Generation."
            )

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
        source_lookup: dict[str, dict[str, object]] = {}

        profile_artifact = await self.storage.put_json(
            key=self._artifact_key(creator=creator, suffix="profile/current.json"),
            payload={
                "creator_id": str(creator.id),
                "platform": creator.platform,
                "handle": creator.handle,
                "profile_url": creator.profile_url,
                "display_name": creator.display_name,
                "bio": creator.bio,
                "followers": creator.followers,
                "language": creator.language,
                "niche_labels": creator.niche_labels,
                "built_at": datetime.now(UTC).isoformat(),
            },
        )
        artifact_uris.append(profile_artifact.source_uri)
        source_lookup[profile_artifact.source_uri] = {
            "artifact_uri": profile_artifact.source_uri,
            "snippet_text": creator.bio,
        }
        await self._store_html_snapshot(
            creator=creator,
            artifact_uris=artifact_uris,
            url=creator.profile_url,
            suffix="profile/page.html",
        )
        await self._store_screenshot_snapshot(
            creator=creator,
            artifact_uris=artifact_uris,
            url=creator.profile_url,
            suffix="profile/page.png",
        )

        snapshot_artifact_uri: str | None = None
        if latest_snapshot is not None:
            snapshot_artifact = await self.storage.put_json(
                key=self._artifact_key(creator=creator, suffix="metrics/latest.json"),
                payload={
                    "snapshot_id": str(latest_snapshot.id),
                    "creator_id": str(creator.id),
                    "captured_at": latest_snapshot.captured_at.isoformat(),
                    "followers": latest_snapshot.follower_count,
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
            snapshot_artifact_uri = snapshot_artifact.source_uri
            artifact_uris.append(snapshot_artifact_uri)
            source_lookup[snapshot_artifact_uri] = {
                "snapshot_id": latest_snapshot.id,
                "artifact_uri": snapshot_artifact_uri,
                "snippet_text": (
                    str(latest_snapshot.average_views_30d)
                    if latest_snapshot.average_views_30d is not None
                    else None
                ),
            }

        content_records: list[EvidenceContentRecord] = []
        existing_brands = sorted(
            {
                brand
                for content in content_items
                for brand in (content.detected_brands or [])
                if brand
            }
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
                    "caption": content.caption,
                    "published_at": (
                        content.published_at.isoformat()
                        if content.published_at is not None
                        else None
                    ),
                    "view_count": content.view_count,
                    "like_count": content.like_count,
                    "comment_count": content.comment_count,
                    "hashtags": content.hashtags,
                    "detected_brands": content.detected_brands,
                    "sponsor_probability": (
                        float(content.sponsor_probability)
                        if content.sponsor_probability is not None
                        else None
                    ),
                    "raw_payload": content.raw_payload,
                },
            )
            artifact_uris.append(content_artifact.source_uri)
            content.raw_snapshot_uri = content_artifact.source_uri
            primary_source_uri = content.url or content_artifact.source_uri
            source_lookup[primary_source_uri] = {
                "content_id": content.id,
                "artifact_uri": content_artifact.source_uri,
                "snippet_text": content.caption or content.title,
            }
            await self._store_html_snapshot(
                creator=creator,
                artifact_uris=artifact_uris,
                url=content.url,
                suffix=f"content/{self._content_key(content)}/page.html",
            )
            await self._store_screenshot_snapshot(
                creator=creator,
                artifact_uris=artifact_uris,
                url=content.url,
                suffix=f"content/{self._content_key(content)}/page.png",
            )
            content_records.append(
                EvidenceContentRecord(
                    title=content.title,
                    caption=content.caption,
                    source_uri=primary_source_uri,
                    source_type=self._content_source_type(creator.platform),
                    hashtags=content.hashtags,
                    detected_brands=content.detected_brands or [],
                    sponsor_probability=(
                        float(content.sponsor_probability)
                        if content.sponsor_probability is not None
                        else None
                    ),
                )
            )

        metrics = {
            "followers": creator.followers,
            "avg_views_30d": creator.avg_views_30d,
            "avg_views_90d": creator.avg_views_90d,
            "avg_engagement_30d": (
                float(creator.avg_engagement_30d)
                if creator.avg_engagement_30d is not None
                else None
            ),
            "metrics_source_uri": snapshot_artifact_uri or profile_artifact.source_uri,
        }
        agent_output = await self.agent_executor.run(
            EvidenceBuilderInput(
                creator_handle=creator.handle,
                platform=creator.platform,
                bio=creator.bio,
                recent_content=content_records,
                metrics=metrics,
                existing_brands=existing_brands,
            )
        )
        if not isinstance(agent_output, EvidenceBuilderOutput):
            raise TypeError("EvidenceBuilder agent output ist nicht vom erwarteten Typ.")

        evidence_results = [
            await self._upsert_evidence_item(
                creator=creator,
                generated_item=item.model_dump(mode="json"),
                source_lookup=source_lookup,
            )
            for item in agent_output.evidence_items
        ]

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

    async def build_brand_evidence_by_domain(self, *, domain: str) -> BrandEvidenceBuildResult:
        """Resolve a brand by domain before building deterministic brand evidence."""

        statement = select(Brand).where(Brand.domain == domain.strip().lower())
        brand = await self.session.scalar(statement)
        if brand is None:
            raise ValueError(f"Brand {domain} wurde nicht gefunden.")
        return await self.build_brand_evidence(brand_id=brand.id)

    async def build_brand_evidence(self, *, brand_id: UUID) -> BrandEvidenceBuildResult:
        """Persist deterministic brand evidence items for future personalization."""

        brand = await self.session.get(Brand, brand_id)
        if brand is None:
            raise ValueError(f"Brand {brand_id} wurde nicht gefunden.")

        artifact_uris = [brand.website_snapshot_uri] if brand.website_snapshot_uri else []
        evidence_results: list[EvidenceItemResult] = []

        if brand.creator_program_score and float(brand.creator_program_score) > 0:
            evidence_results.append(
                await self._upsert_brand_evidence_item(
                    brand=brand,
                    source_type="brand_website",
                    claim_text=(
                        "Brand exposes a creator, affiliate, "
                        "or partner program signal on its website."
                    ),
                    source_uri=brand.website_snapshot_uri or f"brand://{brand.domain}/creator-program",
                    snippet_text=brand.influencer_contact_email or brand.contact_email,
                )
            )
        if brand.influencer_contact_email:
            evidence_results.append(
                await self._upsert_brand_evidence_item(
                    brand=brand,
                    source_type="brand_contact",
                    claim_text=(
                        f"Brand lists {brand.influencer_contact_email} "
                        "as an influencer or partnerships contact."
                    ),
                    source_uri=brand.website_snapshot_uri or f"brand://{brand.domain}/contact",
                    snippet_text=brand.influencer_contact_email,
                )
            )
        if brand.hiring_signal_score and float(brand.hiring_signal_score) > 0:
            evidence_results.append(
                await self._upsert_brand_evidence_item(
                    brand=brand,
                    source_type="hiring_signal",
                    claim_text=(
                        "Brand shows hiring signals for influencer marketing "
                        "or creator partnerships."
                    ),
                    source_uri=f"brand://{brand.domain}/hiring-signal",
                    snippet_text=brand.category,
                )
            )
        if brand.branded_content_score and float(brand.branded_content_score) > 0:
            evidence_results.append(
                await self._upsert_brand_evidence_item(
                    brand=brand,
                    source_type="meta_ad_library",
                    claim_text="Brand shows branded-content or ads-library activity signals.",
                    source_uri=f"brand://{brand.domain}/branded-content",
                    snippet_text=brand.name,
                )
            )
        if brand.spend_intent_score is not None:
            evidence_results.append(
                await self._upsert_brand_evidence_item(
                    brand=brand,
                    source_type="brand_scoring",
                    claim_text=(
                        "Brand spend intent score currently evaluates to "
                        f"{float(brand.spend_intent_score):.4f}."
                    ),
                    source_uri=f"brand://{brand.domain}/spend-intent",
                    snippet_text=brand.category,
                )
            )

        await self.session.flush()
        return BrandEvidenceBuildResult(
            brand_id=str(brand.id),
            domain=brand.domain,
            evidence_count=len(evidence_results),
            artifact_count=len(artifact_uris),
            artifact_uris=artifact_uris,
            evidence_items=evidence_results,
        )

    async def _upsert_evidence_item(
        self,
        *,
        creator: Creator,
        generated_item: dict[str, object],
        source_lookup: dict[str, dict[str, object]],
    ) -> EvidenceItemResult:
        """Insert or update one generated evidence item under a stable key."""

        source_uri = str(generated_item["source_uri"])
        source_type = str(generated_item["source_type"])
        claim_text = str(generated_item["claim_text"])
        confidence = float(generated_item["confidence"])
        lookup = source_lookup.get(source_uri, {})
        source_key = self._source_key(
            creator_id=str(creator.id),
            source_uri=source_uri,
            claim_text=claim_text,
        )

        evidence_item = await self.session.scalar(
            select(EvidenceItem).where(EvidenceItem.source_key == source_key)
        )
        if evidence_item is None:
            evidence_item = EvidenceItem(
                entity_type="creator",
                entity_id=creator.id,
                creator_id=creator.id,
                content_id=lookup.get("content_id"),
                snapshot_id=lookup.get("snapshot_id"),
                source_key=source_key,
                source_type=source_type,
                claim_text=claim_text,
                source_uri=source_uri,
                confidence=confidence,
                artifact_uri=lookup.get("artifact_uri"),
                snippet_text=lookup.get("snippet_text"),
                metadata_json={"creator_handle": creator.handle},
            )
            self.session.add(evidence_item)
        else:
            evidence_item.entity_type = "creator"
            evidence_item.entity_id = creator.id
            evidence_item.creator_id = creator.id
            evidence_item.content_id = lookup.get("content_id")
            evidence_item.snapshot_id = lookup.get("snapshot_id")
            evidence_item.source_type = source_type
            evidence_item.claim_text = claim_text
            evidence_item.source_uri = source_uri
            evidence_item.confidence = confidence
            evidence_item.artifact_uri = lookup.get("artifact_uri")
            evidence_item.snippet_text = lookup.get("snippet_text")
            evidence_item.metadata_json = {"creator_handle": creator.handle}

        await self.session.flush()
        return EvidenceItemResult(
            evidence_id=str(evidence_item.id),
            source_key=evidence_item.source_key,
            source_type=evidence_item.source_type,
            claim_text=evidence_item.claim_text,
            source_uri=evidence_item.source_uri,
            confidence=float(evidence_item.confidence),
            artifact_uri=evidence_item.artifact_uri,
            snippet_text=evidence_item.snippet_text,
        )

    async def _upsert_brand_evidence_item(
        self,
        *,
        brand: Brand,
        source_type: str,
        claim_text: str,
        source_uri: str,
        snippet_text: str | None,
    ) -> EvidenceItemResult:
        """Insert or update one deterministic brand evidence item."""

        source_key = self._brand_source_key(
            brand_id=str(brand.id),
            source_uri=source_uri,
            claim_text=claim_text,
        )
        evidence_item = await self.session.scalar(
            select(EvidenceItem).where(EvidenceItem.source_key == source_key)
        )
        if evidence_item is None:
            evidence_item = EvidenceItem(
                entity_type="brand",
                entity_id=brand.id,
                creator_id=None,
                brand_id=brand.id,
                content_id=None,
                snapshot_id=None,
                source_key=source_key,
                source_type=source_type,
                claim_text=claim_text,
                source_uri=source_uri,
                confidence=0.8,
                artifact_uri=brand.website_snapshot_uri,
                snippet_text=snippet_text,
                metadata_json={"brand_domain": brand.domain},
            )
            self.session.add(evidence_item)
        else:
            evidence_item.entity_type = "brand"
            evidence_item.entity_id = brand.id
            evidence_item.creator_id = None
            evidence_item.brand_id = brand.id
            evidence_item.content_id = None
            evidence_item.snapshot_id = None
            evidence_item.source_type = source_type
            evidence_item.claim_text = claim_text
            evidence_item.source_uri = source_uri
            evidence_item.confidence = 0.8
            evidence_item.artifact_uri = brand.website_snapshot_uri
            evidence_item.snippet_text = snippet_text
            evidence_item.metadata_json = {"brand_domain": brand.domain}

        await self.session.flush()
        return EvidenceItemResult(
            evidence_id=str(evidence_item.id),
            source_key=evidence_item.source_key,
            source_type=evidence_item.source_type,
            claim_text=evidence_item.claim_text,
            source_uri=evidence_item.source_uri,
            confidence=float(evidence_item.confidence),
            artifact_uri=evidence_item.artifact_uri,
            snippet_text=evidence_item.snippet_text,
        )

    def _artifact_key(self, *, creator: Creator, suffix: str) -> str:
        """Build a stable evidence storage key for one creator-scoped artifact."""

        return f"creators/{creator.platform}/{creator.handle}/{suffix}"

    def _content_key(self, content: CreatorContent) -> str:
        """Resolve a stable content artifact key segment."""

        return content.platform_content_id or str(content.id)

    def _content_source_type(self, platform: str) -> str:
        """Map creator platform to the canonical evidence source type."""

        if platform == "youtube":
            return "youtube_video"
        if platform == "instagram":
            return "instagram_post"
        return "tiktok_post"

    def _source_key(self, *, creator_id: str, source_uri: str, claim_text: str) -> str:
        """Build a stable unique key for one generated evidence item."""

        digest = hashlib.sha256(f"{source_uri}|{claim_text}".encode()).hexdigest()[:16]
        return f"creator:{creator_id}:{digest}"

    def _brand_source_key(self, *, brand_id: str, source_uri: str, claim_text: str) -> str:
        """Build a stable unique key for one generated brand evidence item."""

        digest = hashlib.sha256(f"{source_uri}|{claim_text}".encode()).hexdigest()[:16]
        return f"brand:{brand_id}:{digest}"

    async def _store_html_snapshot(
        self,
        *,
        creator: Creator,
        artifact_uris: list[str],
        url: str | None,
        suffix: str,
    ) -> None:
        """Fetch and persist one HTML snapshot when a source URL is available."""

        if not url:
            return

        try:
            html = await self.page_fetcher.fetch_html(url)
        except httpx.HTTPError as exc:
            logger.warning(
                "evidence_html_snapshot_failed",
                creator_id=str(creator.id),
                handle=creator.handle,
                url=url,
                error_message=str(exc),
            )
            return

        artifact = await self.storage.put_text(
            key=self._artifact_key(creator=creator, suffix=suffix),
            payload=html,
            content_type="text/html",
        )
        artifact_uris.append(artifact.source_uri)

    async def _store_screenshot_snapshot(
        self,
        *,
        creator: Creator,
        artifact_uris: list[str],
        url: str | None,
        suffix: str,
    ) -> None:
        """Capture and persist one screenshot snapshot when a source URL is available."""

        if not url:
            return

        try:
            screenshot_bytes = await self.visual_fetcher.capture_png(url)
        except RuntimeError as exc:
            logger.warning(
                "evidence_screenshot_snapshot_failed",
                creator_id=str(creator.id),
                handle=creator.handle,
                url=url,
                error_message=str(exc),
            )
            return

        artifact = await self.storage.put_bytes(
            key=self._artifact_key(creator=creator, suffix=suffix),
            payload=screenshot_bytes,
            content_type="image/png",
        )
        artifact_uris.append(artifact.source_uri)
