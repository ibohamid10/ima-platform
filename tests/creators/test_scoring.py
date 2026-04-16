"""Tests for creator growth tracking and heuristic scoring."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ima.creators.scoring import CreatorGrowthSnapshotInput, CreatorScoringService
from ima.db.models import ConsentStatus, Creator, CreatorContent, CreatorContentType, CreatorPlatform


async def test_scoring_service_qualifies_strong_creator(sqlite_session_factory) -> None:
    """A creator in the target range with healthy growth should qualify."""

    async with sqlite_session_factory() as session:
        creator = Creator(
            platform=CreatorPlatform.YOUTUBE.value,
            handle="fitgrowth",
            display_name="Fit Growth",
            profile_url="https://youtube.com/@fitgrowth",
            bio="Hyrox coach and nutrition creator from Vienna.",
            follower_count=180000,
            consent_status=ConsentStatus.LEGITIMATE_INTEREST.value,
            source_labels=["youtube_api"],
        )
        creator.content_items.extend(
            [
                CreatorContent(
                    content_type=CreatorContentType.VIDEO.value,
                    title=f"Episode {index}",
                    caption_text="Training and nutrition breakdown.",
                    top_hashtags=["hyrox", "fitness", "vienna"],
                    raw_payload={"source": "fixture"},
                )
                for index in range(5)
            ]
        )
        session.add(creator)
        await session.flush()

        service = CreatorScoringService(session)
        await service.record_snapshot(
            CreatorGrowthSnapshotInput(
                creator_id=str(creator.id),
                captured_at=datetime.now(UTC) - timedelta(days=30),
                follower_count=130000,
                average_views_30d=12000,
                engagement_rate_30d=Decimal("0.0410"),
                source="fixture",
            )
        )
        await service.record_snapshot(
            CreatorGrowthSnapshotInput(
                creator_id=str(creator.id),
                captured_at=datetime.now(UTC),
                follower_count=180000,
                average_views_30d=18000,
                engagement_rate_30d=Decimal("0.0450"),
                source="fixture",
            )
        )
        result = await service.score_creator(str(creator.id))
        await session.commit()

    assert result.growth_score >= 80
    assert result.commercial_readiness_score >= 60
    assert result.fraud_risk_score <= 40
    assert result.evidence_coverage_score >= 60
    assert result.is_qualified is True
    assert result.qualification_reasons == []


async def test_scoring_service_flags_unqualified_creator(sqlite_session_factory) -> None:
    """A creator with weak history and sparse evidence should stay unqualified."""

    async with sqlite_session_factory() as session:
        creator = Creator(
            platform=CreatorPlatform.INSTAGRAM.value,
            handle="thinprofile",
            follower_count=25000,
            consent_status=ConsentStatus.UNKNOWN.value,
            source_labels=[],
        )
        session.add(creator)
        await session.flush()

        service = CreatorScoringService(session)
        result = await service.score_creator(str(creator.id))

    assert result.is_qualified is False
    assert "follower_count_outside_phase_1_range" in result.qualification_reasons
    assert "commercial_readiness_below_threshold" in result.qualification_reasons
    assert "evidence_coverage_below_threshold" in result.qualification_reasons
