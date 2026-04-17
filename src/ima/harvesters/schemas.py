"""Schemas for harvested creator source records before canonical ingest."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from ima.creators.schemas import CreatorIngestResult


class HarvestedContentRecord(BaseModel):
    """Raw-ish content record collected by a harvester before canonical ingest."""

    platform_content_id: str | None = None
    content_type: str
    url: str | None = None
    title: str | None = None
    caption_text: str | None = None
    published_at: datetime | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    top_hashtags: list[str] = Field(default_factory=list)
    raw_payload: dict[str, object] | None = None


class HarvestedMetricSnapshotRecord(BaseModel):
    """Metric snapshot collected together with a harvested creator profile."""

    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    follower_count: int | None = None
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
    follower_count: int | None = None
    primary_language: str | None = None
    niche: str | None = None
    sub_niches: list[str] = Field(default_factory=list)
    source_labels: list[str] = Field(default_factory=list)
    metric_snapshot: HarvestedMetricSnapshotRecord | None = None
    content_items: list[HarvestedContentRecord] = Field(default_factory=list)
    raw_payload: dict[str, object] | None = None


class HarvestFixtureBatch(BaseModel):
    """Batch of harvested creator records loaded from a local fixture source."""

    source: str = "fixture"
    batch_id: str | None = None
    creators: list[HarvestedCreatorRecord]


class CreatorSourceImportResult(BaseModel):
    """Structured result for one batch import through the source pipeline."""

    batch_source: str
    batch_id: str | None = None
    total_records: int
    imported_count: int
    via_temporal: bool
    workflow_ids: list[str] = Field(default_factory=list)
    results: list[CreatorIngestResult] = Field(default_factory=list)

