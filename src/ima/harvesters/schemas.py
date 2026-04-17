"""Schemas for harvested creator source records before canonical ingest."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import AliasChoices, BaseModel, Field

from ima.creators.schemas import CreatorIngestResult


class HarvestedContentRecord(BaseModel):
    """Raw-ish content record collected by a harvester before canonical ingest."""

    platform_content_id: str | None = None
    content_type: str
    url: str | None = None
    title: str | None = None
    caption: str | None = Field(
        default=None,
        validation_alias=AliasChoices("caption", "caption_text", "description"),
    )
    published_at: datetime | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    hashtags: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("hashtags", "top_hashtags"),
    )
    detected_brands: list[str] | None = None
    sponsor_probability: float | None = None
    raw_snapshot_uri: str | None = None
    raw_payload: dict[str, object] | None = None


class HarvestedMetricSnapshotRecord(BaseModel):
    """Metric snapshot collected together with a harvested creator profile."""

    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    followers: int | None = Field(
        default=None,
        validation_alias=AliasChoices("followers", "follower_count"),
    )
    average_views_30d: int | None = None
    average_likes_30d: int | None = None
    average_comments_30d: int | None = None
    engagement_rate_30d: Decimal | None = None
    source: str = "fixture"


class HarvestedCreatorRecord(BaseModel):
    """Source record emitted by a harvester before enrichment normalization."""

    source: str = "fixture"
    platform: str
    handle: str
    external_id: str | None = None
    profile_url: str | None = None
    display_name: str | None = None
    bio: str | None = None
    followers: int | None = Field(
        default=None,
        validation_alias=AliasChoices("followers", "follower_count"),
    )
    language: str | None = Field(
        default=None,
        validation_alias=AliasChoices("language", "primary_language"),
    )
    geo: str | None = None
    niche_labels: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("niche_labels", "sub_niches"),
    )
    email: str | None = None
    email_confidence: float | None = None
    source_labels: list[str] = Field(default_factory=list)
    metric_snapshot: HarvestedMetricSnapshotRecord | None = None
    content_items: list[HarvestedContentRecord] = Field(default_factory=list)
    raw_payload: dict[str, object] | None = None


class HarvestFixtureBatch(BaseModel):
    """Batch of harvested creator records loaded from a local fixture source."""

    source: str = "fixture"
    batch_id: str | None = None
    creators: list[HarvestedCreatorRecord]


class YouTubeChannelHarvestRequest(BaseModel):
    """Structured request for harvesting one YouTube channel by stable channel ID."""

    channel_id: str
    max_videos: int = Field(default=5, ge=1, le=50)
    source_labels: list[str] = Field(default_factory=list)


class YouTubeKeywordDiscoveryRequest(BaseModel):
    """Structured request for discovering YouTube channels from keyword searches."""

    keywords: list[str] = Field(min_length=1)
    language: str | None = None
    region: str | None = None
    min_subscribers: int | None = Field(default=None, ge=0)
    max_subscribers: int | None = Field(default=None, ge=0)
    max_results_per_keyword: int = Field(default=5, ge=1, le=25)
    max_videos: int = Field(default=5, ge=1, le=50)
    source_labels: list[str] = Field(default_factory=list)


class CreatorSourceImportResult(BaseModel):
    """Structured result for one batch import through the source pipeline."""

    batch_source: str
    batch_id: str | None = None
    total_records: int
    imported_count: int
    via_temporal: bool
    workflow_ids: list[str] = Field(default_factory=list)
    results: list[CreatorIngestResult] = Field(default_factory=list)
