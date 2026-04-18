"""Tests for deterministic brand evidence building."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from ima.db.models import Brand, EvidenceItem
from ima.evidence.builder import EvidenceBuilderService


@pytest.mark.asyncio()
async def test_brand_evidence_builder_persists_brand_evidence(sqlite_session_factory) -> None:
    """Brand evidence builder should write brand-scoped evidence_items."""

    async with sqlite_session_factory() as session:
        brand = Brand(
            name="Notion",
            domain="notion.so",
            niche_ids=["productivity"],
            geo_markets=["US"],
            creator_program_score=Decimal("0.6000"),
            hiring_signal_score=Decimal("1.0000"),
            branded_content_score=Decimal("0.5000"),
            spend_intent_score=Decimal("0.6750"),
            influencer_contact_email="creators@notion.so",
            website_snapshot_uri="evidence://ima-evidence-dev/brands/notion.so/homepage.html",
        )
        session.add(brand)
        await session.flush()

        result = await EvidenceBuilderService(session=session).build_brand_evidence(
            brand_id=brand.id
        )
        await session.commit()

    async with sqlite_session_factory() as session:
        evidence_items = list(
            (
                await session.scalars(
                    select(EvidenceItem).where(EvidenceItem.entity_type == "brand")
                )
            ).all()
        )

    assert result.evidence_count >= 4
    assert all(item.entity_type == "brand" for item in evidence_items)
    assert all(item.brand_id is not None for item in evidence_items)
