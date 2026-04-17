"""Sandbox-safe Pydantic schemas for creator ingest and scoring flows."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CreatorGrowthSnapshotInput(BaseModel):
    """Structured input for storing a creator metric snapshot."""

    creator_id: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    follower_count: int | None = None
    average_views_30d: int | None = None
    average_likes_30d: int | None = None
    average_comments_30d: int | None = None
    engagement_rate_30d: Decimal | None = None
    source: str = "system"


class CreatorScoreResult(BaseModel):
    """Structured result of the initial creator scoring heuristics."""

    creator_id: str
    growth_score: int
    commercial_readiness_score: int
    fraud_risk_score: int
    evidence_coverage_score: int
    is_qualified: bool
    qualification_reasons: list[str]


class CreatorContentInput(BaseModel):
    """Structured content payload for creator ingest."""

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


class CreatorMetricSnapshotPayload(BaseModel):
    """Structured snapshot payload nested inside creator ingest."""

    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    follower_count: int | None = None
    average_views_30d: int | None = None
    average_likes_30d: int | None = None
    average_comments_30d: int | None = None
    engagement_rate_30d: Decimal | None = None
    source: str = "ingest"


class CreatorIngestInput(BaseModel):
    """Top-level ingest payload for one creator and related source material."""

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
    consent_status: str = "unknown"
    source_labels: list[str] = Field(default_factory=list)
    metric_snapshot: CreatorMetricSnapshotPayload | None = None
    content_items: list[CreatorContentInput] = Field(default_factory=list)


class CreatorIngestResult(BaseModel):
    """Structured result of one creator ingest run."""

    creator_id: str
    created: bool
    content_created: int
    content_updated: int
    snapshot_recorded: bool
    score: CreatorScoreResult
