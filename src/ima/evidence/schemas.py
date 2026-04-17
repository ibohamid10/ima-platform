"""Schemas for evidence artifacts, evidence items, and build results."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class StoredArtifact(BaseModel):
    """Structured metadata returned by the evidence storage adapter."""

    storage_key: str
    source_uri: str
    content_type: str
    byte_size: int
    sha256: str
    local_path: str | None = None


class EvidenceItemResult(BaseModel):
    """Serializable result for one persisted evidence item."""

    evidence_id: str
    source_key: str
    evidence_type: str
    claim_text: str
    source_uri: str
    artifact_uri: str | None = None
    snippet_text: str | None = None


class EvidenceBuildResult(BaseModel):
    """Summary of one creator evidence build run."""

    creator_id: str
    platform: str
    handle: str
    built_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evidence_count: int
    artifact_count: int
    artifact_uris: list[str]
    evidence_items: list[EvidenceItemResult]
