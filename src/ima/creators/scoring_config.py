"""Configurable creator scoring thresholds and weights."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ima.config import settings


class NicheFitConfig(BaseModel):
    """Weights for matching target niche and target sub-niches."""

    primary_label_weight: float = 0.7
    sub_label_weight: float = 0.3


class GrowthConfig(BaseModel):
    """Thresholds and score outputs for growth scoring."""

    neutral_score: float = 0.5
    strong_growth_ratio: float = 0.30
    strong_growth_score: float = 0.9
    solid_growth_ratio: float = 0.20
    solid_growth_score: float = 0.8
    healthy_growth_ratio: float = 0.10
    healthy_growth_score: float = 0.7
    mild_growth_ratio: float = 0.03
    mild_growth_score: float = 0.6
    flat_band_ratio: float = -0.03
    flat_band_score: float = 0.5
    decline_band_ratio: float = -0.10
    decline_band_score: float = 0.35
    steep_decline_score: float = 0.2
    healthy_view_ratio_bonus_threshold: float = 0.08
    healthy_view_ratio_bonus: float = 0.05


class CommercialConfig(BaseModel):
    """Weights for commercial readiness scoring."""

    base_score: float = 0.25
    bio_bonus: float = 0.15
    profile_url_bonus: float = 0.15
    display_name_bonus: float = 0.05
    external_id_bonus: float = 0.05
    target_range_bonus: float = 0.20
    fallback_range_bonus: float = 0.10
    target_min_followers: int = 100000
    target_max_followers: int = 1000000
    fallback_min_followers: int = 25000
    strong_content_count: int = 5
    medium_content_count: int = 3
    strong_content_bonus: float = 0.15
    medium_content_bonus: float = 0.10
    url_bonus: float = 0.05


class FraudConfig(BaseModel):
    """Thresholds for fraud-risk heuristics."""

    base_risk: float = 0.15
    no_content_penalty: float = 0.25
    low_view_ratio_threshold: float = 0.005
    low_view_ratio_penalty: float = 0.35
    medium_view_ratio_threshold: float = 0.01
    medium_view_ratio_penalty: float = 0.20
    repetitive_hashtag_penalty: float = 0.10


class EvidenceCoverageConfig(BaseModel):
    """Weights for evidence coverage scoring."""

    bio_weight: float = 0.20
    profile_url_weight: float = 0.20
    followers_weight: float = 0.20
    content_weight: float = 0.20
    raw_payload_weight: float = 0.20
    minimum_content_items: int = 3


class QualificationConfig(BaseModel):
    """Thresholds for the first creator qualification decision."""

    min_growth_score: float = 0.60
    min_niche_fit_score: float = 0.50
    min_commercial_score: float = 0.60
    max_fraud_score: float = 0.40
    min_evidence_coverage_score: float = 0.60
    min_followers: int = 100000
    max_followers: int = 1000000


class ScoringConfig(BaseModel):
    """Top-level configurable scoring defaults."""

    target_niche: str = "fitness"
    target_sub_niches: list[str] = Field(default_factory=lambda: ["hyrox", "nutrition"])
    niche_fit: NicheFitConfig = Field(default_factory=NicheFitConfig)
    growth: GrowthConfig = Field(default_factory=GrowthConfig)
    commercial: CommercialConfig = Field(default_factory=CommercialConfig)
    fraud: FraudConfig = Field(default_factory=FraudConfig)
    evidence_coverage: EvidenceCoverageConfig = Field(default_factory=EvidenceCoverageConfig)
    qualification: QualificationConfig = Field(default_factory=QualificationConfig)


@lru_cache(maxsize=1)
def load_scoring_config(path: str | None = None) -> ScoringConfig:
    """Load scoring configuration from YAML with repo defaults."""

    config_path = Path(path or settings.scoring_config_path)
    if not config_path.exists():
        return ScoringConfig()

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return ScoringConfig.model_validate(payload)
