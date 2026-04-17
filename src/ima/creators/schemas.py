"""Sandbox-safe Pydantic schemas for creator ingest and scoring flows."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import AliasChoices, BaseModel, Field


class CreatorGrowthSnapshotInput(BaseModel):
    """Structured input for storing a creator metric snapshot."""

    creator_id: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    followers: int | None = Field(
        default=None,
        validation_alias=AliasChoices("followers", "follower_count"),
    )
    average_views_30d: int | None = None
    average_likes_30d: int | None = None
    average_comments_30d: int | None = None
    engagement_rate_30d: Decimal | None = None
    source: str = "system"


class CreatorScoreResult(BaseModel):
    """Structured result of the initial creator scoring heuristics."""

    creator_id: str
    growth_score: float
    niche_fit_score: float = Field(
        default=0.0,
        validation_alias=AliasChoices("niche_fit_score"),
    )
    commercial_score: float = Field(
        validation_alias=AliasChoices("commercial_score", "commercial_readiness_score"),
    )
    fraud_score: float = Field(
        validation_alias=AliasChoices("fraud_score", "fraud_risk_score"),
    )
    evidence_coverage_score: float
    is_qualified: bool
    qualification_reasons: list[str]


class CreatorContentInput(BaseModel):
    """Structured content payload for creator ingest."""

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


class CreatorMetricSnapshotPayload(BaseModel):
    """Structured snapshot payload nested inside creator ingest."""

    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    followers: int | None = Field(
        default=None,
        validation_alias=AliasChoices("followers", "follower_count"),
    )
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
    consent_basis: str = Field(
        default="unknown",
        validation_alias=AliasChoices("consent_basis", "consent_status"),
    )
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
