"""Database model tests for week-2 creator tables."""

from __future__ import annotations

from sqlalchemy import Numeric, select

from ima.db.models import (
    AgentRun,
    Brand,
    BrandCreatorMatch,
    ConsentStatus,
    Creator,
    CreatorContent,
    CreatorContentType,
    CreatorNicheScore,
    CreatorPlatform,
    EvidenceItem,
    SuppressionManual,
)


def test_fixed_point_score_columns_use_numeric_precision() -> None:
    """Critical score fields should remain fixed-point numerics in the ORM."""

    expected_columns = {
        Creator.__table__.c.avg_engagement_30d: (8, 4),
        Creator.__table__.c.growth_score: (6, 4),
        Creator.__table__.c.niche_fit_score: (6, 4),
        Creator.__table__.c.commercial_score: (6, 4),
        Creator.__table__.c.fraud_score: (6, 4),
        Creator.__table__.c.evidence_coverage_score: (6, 4),
        Creator.__table__.c.email_confidence: (6, 4),
        CreatorNicheScore.__table__.c.niche_fit_score: (6, 4),
        CreatorContent.__table__.c.sponsor_probability: (6, 4),
        EvidenceItem.__table__.c.confidence: (6, 4),
    }
    for column, (precision, scale) in expected_columns.items():
        assert isinstance(column.type, Numeric)
        assert column.type.precision == precision
        assert column.type.scale == scale


def test_agent_run_budget_columns_use_numeric_precision() -> None:
    """Agent-run budget fields should remain fixed-point numerics."""

    for column_name, (precision, scale) in {
        "cost_usd": (12, 6),
        "reserved_cost_usd": (12, 6),
    }.items():
        column = AgentRun.__table__.c[column_name]
        assert isinstance(column.type, Numeric)
        assert column.type.precision == precision
        assert column.type.scale == scale
    assert isinstance(BrandCreatorMatch.__table__.c.match_score.type, Numeric)
    assert BrandCreatorMatch.__table__.c.match_score.type.precision == 6
    assert BrandCreatorMatch.__table__.c.match_score.type.scale == 4


def test_brand_numeric_columns_use_fixed_point_precision() -> None:
    """Brand scoring fields should stay fixed-point numerics."""

    expected_columns = {
        Brand.__table__.c.spend_intent_score: (6, 4),
        Brand.__table__.c.branded_content_score: (6, 4),
        Brand.__table__.c.hiring_signal_score: (6, 4),
        Brand.__table__.c.creator_program_score: (6, 4),
        Brand.__table__.c.contact_confidence: (6, 4),
        BrandCreatorMatch.__table__.c.niche_fit_component: (6, 4),
        BrandCreatorMatch.__table__.c.audience_alignment_component: (6, 4),
        BrandCreatorMatch.__table__.c.commercial_readiness_component: (6, 4),
        BrandCreatorMatch.__table__.c.brand_spend_intent_component: (6, 4),
        BrandCreatorMatch.__table__.c.geo_fit_component: (6, 4),
        BrandCreatorMatch.__table__.c.competitor_penalty_component: (6, 4),
        BrandCreatorMatch.__table__.c.growth_momentum_component: (6, 4),
    }
    for column, (precision, scale) in expected_columns.items():
        assert isinstance(column.type, Numeric)
        assert column.type.precision == precision
        assert column.type.scale == scale


async def test_creator_and_content_relationship(sqlite_session_factory) -> None:
    """Creator content should persist and load through the ORM relationship."""

    async with sqlite_session_factory() as session:
        creator = Creator(
            platform=CreatorPlatform.YOUTUBE.value,
            handle="fitnessfranz",
            profile_url="https://youtube.com/@fitnessfranz",
            bio="Hyrox Athlet aus Wien",
            followers=125000,
            consent_basis=ConsentStatus.LEGITIMATE_INTEREST.value,
            source_labels=["youtube_api"],
        )
        creator.content_items.append(
            CreatorContent(
                content_type=CreatorContentType.VIDEO.value,
                platform_content_id="yt-123",
                title="Hyrox PR in Wien",
                caption="Neue Bestzeit im Training.",
                hashtags=["hyrox", "fitness", "wien"],
                raw_payload={"source": "fixture"},
            )
        )
        session.add(creator)
        await session.commit()

    async with sqlite_session_factory() as session:
        stored_creator = await session.scalar(
            select(Creator).where(Creator.handle == "fitnessfranz")
        )

    assert stored_creator is not None
    assert stored_creator.platform == CreatorPlatform.YOUTUBE.value
    assert stored_creator.consent_basis == ConsentStatus.LEGITIMATE_INTEREST.value
    assert len(stored_creator.content_items) == 1
    assert stored_creator.content_items[0].content_type == CreatorContentType.VIDEO.value


async def test_brand_and_suppression_models_persist(sqlite_session_factory) -> None:
    """Brand and suppression tables should be creatable via ORM metadata."""

    async with sqlite_session_factory() as session:
        brand = Brand(
            name="Notion",
            domain="notion.so",
            category="SaaS",
            niche_ids=["productivity", "tech"],
            geo_markets=["US", "DE"],
            consent_basis="public_business_contact",
        )
        session.add(brand)
        session.add(
            SuppressionManual(
                email="blocked@example.com",
                entity_type="brand_contact",
                reason="Manual block",
            )
        )
        await session.commit()

    async with sqlite_session_factory() as session:
        stored_brand = await session.scalar(select(Brand).where(Brand.domain == "notion.so"))
        stored_suppression = await session.scalar(
            select(SuppressionManual).where(SuppressionManual.email == "blocked@example.com")
        )

    assert stored_brand is not None
    assert stored_brand.niche_ids == ["productivity", "tech"]
    assert stored_suppression is not None
