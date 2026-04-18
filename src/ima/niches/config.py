"""Structured niche configuration loaded from YAML files."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class NicheDiscoveryConfig(BaseModel):
    """Discovery hints and filters for one niche."""

    youtube_keywords: list[str] = Field(default_factory=list, min_length=1)
    hashtag_seeds: list[str] = Field(default_factory=list)
    min_subscribers: int | None = Field(default=None, ge=0)
    max_subscribers: int | None = Field(default=None, ge=0)
    languages: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)


class NicheFitScoringConfig(BaseModel):
    """Label-level niche fit scoring weights."""

    primary_labels: list[str] = Field(default_factory=list, min_length=1)
    secondary_labels: list[str] = Field(default_factory=list)
    primary_weight: float = Field(default=0.6, ge=0.0)
    secondary_weight: float = Field(default=0.4, ge=0.0)

    @field_validator("primary_labels", "secondary_labels")
    @classmethod
    def normalize_labels(cls, value: list[str]) -> list[str]:
        """Normalize label arrays to lower-case trimmed values."""

        return [item.strip().lower() for item in value if item and item.strip()]


class NicheScoringConfig(BaseModel):
    """Scoring-related settings for one niche."""

    niche_fit: NicheFitScoringConfig


class NicheBrandSignalsConfig(BaseModel):
    """Brand-side signals associated with one niche."""

    categories: list[str] = Field(default_factory=list)
    keywords_creator_programs: list[str] = Field(default_factory=list)
    keywords_hiring: list[str] = Field(default_factory=list)


class NicheConfig(BaseModel):
    """Top-level niche configuration document."""

    niche_id: str
    display_name: str
    discovery: NicheDiscoveryConfig
    scoring: NicheScoringConfig
    brand_signals: NicheBrandSignalsConfig

    @field_validator("niche_id")
    @classmethod
    def validate_niche_id(cls, value: str) -> str:
        """Keep niche identifiers stable and slug-like."""

        normalized = value.strip().lower().replace(" ", "-")
        if not normalized:
            raise ValueError("niche_id darf nicht leer sein.")
        return normalized
