"""Tests for creator growth tracking and heuristic scoring."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from ima.creators.scoring import CreatorGrowthSnapshotInput, CreatorScoringService
from ima.db.models import (
    ConsentBasis,
    Creator,
    CreatorContent,
    CreatorContentType,
    CreatorMetricSnapshot,
    CreatorPlatform,
)


async def test_scoring_service_qualifies_strong_creator(sqlite_session_factory) -> None:
    """A creator in the target range with healthy growth should qualify."""

    async with sqlite_session_factory() as session:
        creator = Creator(
            platform=CreatorPlatform.YOUTUBE.value,
            handle="fitgrowth",
            display_name="Fit Growth",
            profile_url="https://youtube.com/@fitgrowth",
            bio="Hyrox coach and nutrition creator from Vienna.",
            followers=180000,
            niche_labels=["fitness", "hyrox", "nutrition"],
            consent_basis=ConsentBasis.LEGITIMATE_INTEREST.value,
            source_labels=["youtube_api"],
        )
        creator.content_items.extend(
            [
                CreatorContent(
                    content_type=CreatorContentType.VIDEO.value,
                    title=f"Episode {index}",
                    caption="Training and nutrition breakdown.",
                    hashtags=["hyrox", "fitness", "vienna"],
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
                followers=130000,
                average_views_30d=12000,
                engagement_rate_30d=Decimal("0.0410"),
                source="fixture",
            )
        )
        await service.record_snapshot(
            CreatorGrowthSnapshotInput(
                creator_id=str(creator.id),
                captured_at=datetime.now(UTC),
                followers=180000,
                average_views_30d=18000,
                engagement_rate_30d=Decimal("0.0450"),
                source="fixture",
            )
        )
        result = await service.score_creator(str(creator.id))
        await session.commit()

    assert result.growth_score >= 0.8
    assert result.niche_fit_score >= 0.7
    assert result.commercial_score >= 0.6
    assert result.fraud_score <= 0.4
    assert result.evidence_coverage_score >= 0.6
    assert result.is_qualified is True
    assert result.qualification_reasons == []


async def test_scoring_service_flags_unqualified_creator(sqlite_session_factory) -> None:
    """A creator with weak history and sparse evidence should stay unqualified."""

    async with sqlite_session_factory() as session:
        creator = Creator(
            platform=CreatorPlatform.INSTAGRAM.value,
            handle="thinprofile",
            followers=25000,
            consent_basis=ConsentBasis.UNKNOWN.value,
            niche_labels=[],
            source_labels=[],
        )
        session.add(creator)
        await session.flush()

        service = CreatorScoringService(session)
        result = await service.score_creator(str(creator.id))

    assert result.is_qualified is False
    assert "followers_outside_phase_1_range" in result.qualification_reasons
    assert "commercial_below_threshold" in result.qualification_reasons
    assert "evidence_coverage_below_threshold" in result.qualification_reasons


async def test_record_snapshot_is_idempotent_per_creator_day(sqlite_session_factory) -> None:
    """Recording the same creator-day snapshot twice should update instead of duplicating."""

    async with sqlite_session_factory() as session:
        creator = Creator(
            platform=CreatorPlatform.YOUTUBE.value,
            handle="snapidempotent",
            followers=150000,
            niche_labels=["fitness"],
        )
        session.add(creator)
        await session.flush()

        service = CreatorScoringService(session)
        first = await service.record_snapshot(
            CreatorGrowthSnapshotInput(
                creator_id=str(creator.id),
                captured_at=datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
                followers=150000,
                average_views_30d=10000,
                source="fixture",
            )
        )
        second = await service.record_snapshot(
            CreatorGrowthSnapshotInput(
                creator_id=str(creator.id),
                captured_at=datetime(2026, 4, 17, 18, 0, tzinfo=UTC),
                followers=151000,
                average_views_30d=12000,
                source="fixture",
            )
        )
        await session.commit()

        snapshots = list(
            (
                await session.scalars(
                    select(CreatorMetricSnapshot).where(
                        CreatorMetricSnapshot.creator_id == creator.id
                    )
                )
            ).all()
        )

    assert first.id == second.id
    assert len(snapshots) == 1
    assert snapshots[0].follower_count == 151000
    assert snapshots[0].average_views_30d == 12000
