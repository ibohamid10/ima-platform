"""SQLAlchemy models for the current database footprint."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models."""


class ValidationStatus(StrEnum):
    """Validation states for agent runs."""

    PENDING = "pending"
    SUCCESS = "success"
    SCHEMA_RETRY = "schema_retry"
    SCHEMA_FAILED = "schema_failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_ERROR = "provider_error"


class CreatorPlatform(StrEnum):
    """Supported creator platforms for phase 1."""

    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class CreatorContentType(StrEnum):
    """Supported content buckets for stored creator items."""

    VIDEO = "video"
    SHORT = "short"
    POST = "post"
    REEL = "reel"
    TIKTOK = "tiktok"


class ConsentBasis(StrEnum):
    """Consent basis tracking for creator outreach eligibility."""

    UNKNOWN = "unknown"
    LEGITIMATE_INTEREST = "legitimate_interest"
    CONSENTED = "consented"
    SUPPRESSED = "suppressed"


ConsentStatus = ConsentBasis
JSONType = JSON().with_variant(JSONB, "postgresql")


class AgentRun(Base):
    """Audit record for every agent execution."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_agent_name", "agent_name"),
        Index("ix_agent_runs_started_at", "started_at"),
        Index("ix_agent_runs_validation_status", "validation_status"),
    )

    id: Mapped[UUID] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_json: Mapped[dict[str, object]] = mapped_column(JSONType, nullable=False)
    output_json: Mapped[dict[str, object] | None] = mapped_column(JSONType, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    reserved_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class Creator(Base):
    """Canonical creator record used by discovery, scoring, and outreach flows."""

    __tablename__ = "creators"
    __table_args__ = (
        Index("ix_creators_platform_handle", "platform", "handle", unique=True),
        Index("ix_creators_qualified", "is_qualified"),
        Index("ix_creators_last_seen_at", "last_seen_at"),
    )

    id: Mapped[UUID] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    handle: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    followers: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    niche_labels: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    geo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    avg_views_30d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    avg_views_90d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    avg_engagement_30d: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    growth_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    niche_fit_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    commercial_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    fraud_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    evidence_coverage_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    consent_basis: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        default=ConsentBasis.UNKNOWN.value,
    )
    consent_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_labels: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    is_qualified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    content_items: Mapped[list[CreatorContent]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    metric_snapshots: Mapped[list[CreatorMetricSnapshot]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    niche_scores: Mapped[list[CreatorNicheScore]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CreatorNicheScore(Base):
    """Per-niche fit breakdown for creators with a best-score shortcut on creators."""

    __tablename__ = "creator_niche_scores"
    __table_args__ = (
        Index("ix_creator_niche_scores_creator_id_niche_id", "creator_id", "niche_id", unique=True),
        Index("ix_creator_niche_scores_niche_id", "niche_id"),
        Index("ix_creator_niche_scores_niche_fit_score", "niche_fit_score"),
    )

    id: Mapped[UUID] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    creator_id: Mapped[UUID] = mapped_column(
        SAUuid,
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
    )
    niche_id: Mapped[str] = mapped_column(String(64), nullable=False)
    niche_fit_score: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    creator: Mapped[Creator] = relationship(back_populates="niche_scores", lazy="selectin")


class CreatorContent(Base):
    """Stored creator content used for scoring, evidence building, and classification."""

    __tablename__ = "creator_content"
    __table_args__ = (
        Index("ix_creator_content_creator_id_published_at", "creator_id", "published_at"),
        Index("ix_creator_content_platform_content_id", "platform_content_id"),
    )

    id: Mapped[UUID] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    creator_id: Mapped[UUID] = mapped_column(
        SAUuid,
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform_content_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    view_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    like_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    hashtags: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    detected_brands: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)
    sponsor_probability: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    raw_snapshot_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, object] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    creator: Mapped[Creator] = relationship(back_populates="content_items", lazy="selectin")


class CreatorMetricSnapshot(Base):
    """Historical creator metrics used for trajectory-aware growth scoring."""

    __tablename__ = "creator_metric_snapshots"
    __table_args__ = (
        Index("ix_creator_metric_snapshots_creator_id_captured_at", "creator_id", "captured_at"),
    )

    id: Mapped[UUID] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    creator_id: Mapped[UUID] = mapped_column(
        SAUuid,
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    follower_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    average_views_30d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    average_likes_30d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    average_comments_30d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    engagement_rate_30d: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    creator: Mapped[Creator] = relationship(back_populates="metric_snapshots", lazy="selectin")


class EvidenceItem(Base):
    """Persisted evidence coverage entry tied to creator data and stored artifacts."""

    __tablename__ = "evidence_items"
    __table_args__ = (
        Index("ix_evidence_items_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_evidence_items_creator_id", "creator_id"),
        Index("ix_evidence_items_brand_id", "brand_id"),
        Index("ix_evidence_items_content_id", "content_id"),
        Index("ix_evidence_items_snapshot_id", "snapshot_id"),
    )

    id: Mapped[UUID] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, default="creator")
    entity_id: Mapped[UUID] = mapped_column(SAUuid, nullable=False)
    creator_id: Mapped[UUID | None] = mapped_column(
        SAUuid,
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=True,
    )
    brand_id: Mapped[UUID | None] = mapped_column(
        SAUuid,
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=True,
    )
    content_id: Mapped[UUID | None] = mapped_column(
        SAUuid,
        ForeignKey("creator_content.id", ondelete="CASCADE"),
        nullable=True,
    )
    snapshot_id: Mapped[UUID | None] = mapped_column(
        SAUuid,
        ForeignKey("creator_metric_snapshots.id", ondelete="CASCADE"),
        nullable=True,
    )
    source_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=1.0)
    artifact_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    snippet_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class Brand(Base):
    """Canonical brand record used for spend-intent scoring and future matching."""

    __tablename__ = "brands"
    __table_args__ = (
        Index("ix_brands_domain", "domain", unique=True),
        Index("ix_brands_category", "category"),
        Index("ix_brands_niche_ids", "niche_ids"),
        Index("ix_brands_spend_intent_score", "spend_intent_score"),
    )

    id: Mapped[UUID] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    niche_ids: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    geo_markets: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    spend_intent_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    branded_content_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    hiring_signal_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    creator_program_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    influencer_contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_confidence: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    website_snapshot_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_basis: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    matches: Mapped[list[BrandCreatorMatch]] = relationship(
        back_populates="brand",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class BrandCreatorMatch(Base):
    """Prepared match rows between brands and creators for week-4 review flows."""

    __tablename__ = "brand_creator_matches"
    __table_args__ = (
        Index("ix_brand_creator_matches_brand_creator", "brand_id", "creator_id", unique=True),
        Index("ix_brand_creator_matches_niche_id", "niche_id"),
        Index("ix_brand_creator_matches_match_score", "match_score"),
        Index("ix_brand_creator_matches_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    brand_id: Mapped[UUID] = mapped_column(
        SAUuid,
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    creator_id: Mapped[UUID] = mapped_column(
        SAUuid,
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
    )
    niche_id: Mapped[str] = mapped_column(String(64), nullable=False)
    match_score: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    niche_fit_component: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    audience_alignment_component: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    commercial_readiness_component: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    brand_spend_intent_component: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    geo_fit_component: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    competitor_penalty_component: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    growth_momentum_component: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    best_angle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    offer_shape: Mapped[str | None] = mapped_column(String(255), nullable=True)
    conflict_flags: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)
    rationale_json: Mapped[dict[str, object] | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    brand: Mapped[Brand] = relationship(back_populates="matches", lazy="selectin")
    creator: Mapped[Creator] = relationship(lazy="selectin")


class SuppressionBase(Base):
    """Shared suppression table columns."""

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(SAUuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(SAUuid, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class SuppressionUnsubscribe(SuppressionBase):
    """Permanent suppression after an unsubscribe event."""

    __tablename__ = "suppression_unsubscribe"
    __table_args__ = (Index("ix_suppression_unsubscribe_email", "email", unique=True),)


class SuppressionHardBounce(SuppressionBase):
    """Permanent suppression after a hard bounce."""

    __tablename__ = "suppression_hard_bounce"
    __table_args__ = (Index("ix_suppression_hard_bounce_email", "email", unique=True),)


class SuppressionSpamComplaint(SuppressionBase):
    """Permanent suppression after a spam complaint."""

    __tablename__ = "suppression_spam_complaint"
    __table_args__ = (Index("ix_suppression_spam_complaint_email", "email", unique=True),)


class SuppressionWrongPerson(SuppressionBase):
    """Permanent suppression for wrong-person replies."""

    __tablename__ = "suppression_wrong_person"
    __table_args__ = (Index("ix_suppression_wrong_person_email", "email", unique=True),)


class SuppressionManual(SuppressionBase):
    """Manual suppression inserted by the operator."""

    __tablename__ = "suppression_manual"
    __table_args__ = (Index("ix_suppression_manual_email", "email", unique=True),)
