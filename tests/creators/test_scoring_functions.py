"""Isolated unit tests for creator scoring helper functions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ima.creators.scoring import (
    compute_commercial_readiness,
    compute_evidence_coverage,
    compute_fraud_risk,
    compute_growth_score,
    compute_niche_fit,
)
from ima.creators.scoring_config import ScoringConfig
from ima.db.models import Creator, CreatorContent, CreatorMetricSnapshot


def _creator(**overrides: object) -> Creator:
    """Build a detached creator instance for isolated scoring tests."""

    payload: dict[str, object] = {
        "platform": "youtube",
        "handle": "creator-test",
        "followers": 180000,
        "profile_url": "https://example.test/@creator-test",
        "display_name": "Creator Test",
        "bio": "Hyrox coach and nutrition creator.",
        "niche_labels": ["fitness", "hyrox", "nutrition"],
    }
    payload.update(overrides)
    return Creator(**payload)


def _content(**overrides: object) -> CreatorContent:
    """Build a detached content instance for isolated scoring tests."""

    payload: dict[str, object] = {
        "creator_id": _creator().id,
        "content_type": "video",
        "title": "Training breakdown",
        "caption": "Hyrox session and nutrition recap.",
        "hashtags": ["hyrox", "fitness"],
        "raw_payload": {"fixture": True},
    }
    payload.update(overrides)
    return CreatorContent(**payload)


def _snapshot(
    *,
    days_ago: int,
    followers: int,
    views: int,
    engagement: float,
) -> CreatorMetricSnapshot:
    """Build a detached historical metric snapshot."""

    return CreatorMetricSnapshot(
        creator_id=_creator().id,
        captured_at=datetime.now(UTC) - timedelta(days=days_ago),
        follower_count=followers,
        average_views_30d=views,
        engagement_rate_30d=engagement,
        source="fixture",
    )


def test_compute_niche_fit_exact_match() -> None:
    """Exact target niche plus sub-niche overlap should score at the top end."""

    score = compute_niche_fit(
        _creator(),
        "fitness",
        ["hyrox", "nutrition"],
        primary_label_weight=0.7,
        sub_label_weight=0.3,
    )

    assert score == 1.0


def test_compute_niche_fit_partial_match() -> None:
    """Partial overlap should score between zero and one."""

    score = compute_niche_fit(
        _creator(niche_labels=["fitness", "running"]),
        "fitness",
        ["hyrox", "nutrition"],
        primary_label_weight=0.7,
        sub_label_weight=0.3,
    )

    assert 0.7 <= score < 1.0


def test_compute_niche_fit_no_match() -> None:
    """No overlap should score zero."""

    score = compute_niche_fit(
        _creator(niche_labels=["tech", "saas"]),
        "fitness",
        ["hyrox", "nutrition"],
        primary_label_weight=0.7,
        sub_label_weight=0.3,
    )

    assert score == 0.0


def test_compute_growth_score_growing_creator() -> None:
    """Strong positive trajectory should produce a high growth score."""

    config = ScoringConfig()
    score = compute_growth_score(
        _creator(followers=180000),
        [
            _snapshot(days_ago=30, followers=120000, views=9000, engagement=0.03),
            _snapshot(days_ago=0, followers=180000, views=22000, engagement=0.05),
        ],
        config,
    )

    assert score >= 0.8


def test_compute_growth_score_stagnating_creator() -> None:
    """Flat or declining trajectory should remain near the neutral band."""

    config = ScoringConfig()
    score = compute_growth_score(
        _creator(followers=120000),
        [
            _snapshot(days_ago=30, followers=120000, views=3000, engagement=0.01),
            _snapshot(days_ago=0, followers=118000, views=2800, engagement=0.01),
        ],
        config,
    )

    assert score <= 0.5


def test_compute_commercial_readiness_ready_creator() -> None:
    """Strong profile completeness plus enough content should look commercially ready."""

    config = ScoringConfig()
    score = compute_commercial_readiness(
        _creator(),
        [_content() for _ in range(5)],
        config,
    )

    assert score >= 0.8


def test_compute_commercial_readiness_not_ready_creator() -> None:
    """Sparse profile information should stay below the qualification threshold."""

    config = ScoringConfig()
    score = compute_commercial_readiness(
        _creator(
            followers=15000,
            profile_url=None,
            display_name=None,
            bio=None,
            external_id=None,
        ),
        [],
        config,
    )

    assert score < config.qualification.min_commercial_score


def test_compute_fraud_risk_clean_creator() -> None:
    """Healthy view ratios and diverse hashtags should keep fraud risk low."""

    config = ScoringConfig()
    score = compute_fraud_risk(
        _creator(followers=180000),
        [_snapshot(days_ago=0, followers=180000, views=20000, engagement=0.04)],
        [_content(hashtags=["hyrox", "training"]), _content(hashtags=["nutrition", "recovery"])],
        config,
    )

    assert score <= 0.35


def test_compute_fraud_risk_suspicious_creator() -> None:
    """Very low view ratios and repetitive hashtags should increase fraud risk."""

    config = ScoringConfig()
    score = compute_fraud_risk(
        _creator(followers=500000),
        [_snapshot(days_ago=0, followers=500000, views=1000, engagement=0.002)],
        [_content(hashtags=["viral", "viral", "viral"]), _content(hashtags=["viral", "viral"])],
        config,
    )

    assert score >= config.qualification.max_fraud_score


def test_compute_evidence_coverage_complete() -> None:
    """Complete structured source material should lead to full coverage."""

    config = ScoringConfig()
    score = compute_evidence_coverage(_creator(), [_content() for _ in range(3)], config)

    assert score == 1.0


def test_compute_evidence_coverage_sparse() -> None:
    """Missing profile signals and raw payloads should reduce coverage."""

    config = ScoringConfig()
    score = compute_evidence_coverage(
        _creator(profile_url=None, bio=None, followers=None),
        [_content(raw_payload=None)],
        config,
    )

    assert score < config.qualification.min_evidence_coverage_score
