"""SQLAlchemy models for the week-1 database footprint."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
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
