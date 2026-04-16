"""SQLAlchemy models for the current database footprint."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
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


class ConsentStatus(StrEnum):
    """Consent tracking status for creator outreach eligibility."""

    UNKNOWN = "unknown"
    LEGITIMATE_INTEREST = "legitimate_interest"
    CONSENTED = "consented"
    SUPPRESSED = "suppressed"


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
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
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
    profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    follower_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    primary_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    niche: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sub_niches: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    growth_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commercial_readiness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fraud_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_coverage_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consent_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ConsentStatus.UNKNOWN.value,
    )
    consent_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_labels: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    is_qualified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    content_items: Mapped[list["CreatorContent"]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    metric_snapshots: Mapped[list["CreatorMetricSnapshot"]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


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
    caption_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    view_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    like_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    top_hashtags: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    raw_payload: Mapped[dict[str, object] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
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
        default=lambda: datetime.now(timezone.utc),
    )

    creator: Mapped[Creator] = relationship(back_populates="metric_snapshots", lazy="selectin")
