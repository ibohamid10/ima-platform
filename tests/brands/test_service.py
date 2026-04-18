"""Tests for brand CRUD helpers."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from ima.brands.service import BrandService, BrandUpsertInput
from ima.db.models import Brand


@pytest.mark.asyncio()
async def test_brand_service_create_update_and_get_by_domain(sqlite_session_factory) -> None:
    """Brand service should create, update, and reload brands by unique domain."""

    async with sqlite_session_factory() as session:
        service = BrandService(session)
        brand, created = await service.upsert_brand(
            BrandUpsertInput(
                name="Notion",
                domain="notion.so",
                category="SaaS",
                niche_ids=["productivity"],
                geo_markets=["US", "DE"],
                consent_basis="public_business_contact",
            )
        )
        await session.commit()

        assert created is True
        assert brand.domain == "notion.so"

    async with sqlite_session_factory() as session:
        service = BrandService(session)
        brand, created = await service.upsert_brand(
            BrandUpsertInput(
                name="Notion Labs",
                domain="https://notion.so/",
                category="Productivity Software",
                niche_ids=["productivity", "tech"],
                geo_markets=["US", "DE", "GB"],
                consent_basis="public_business_contact",
            )
        )
        await session.commit()

        assert created is False
        stored = await service.get_by_domain("notion.so")

    assert brand.name == "Notion Labs"
    assert stored is not None
    assert stored.category == "Productivity Software"
    assert stored.niche_ids == ["productivity", "tech"]


@pytest.mark.asyncio()
async def test_brand_service_lists_brands_in_name_order(sqlite_session_factory) -> None:
    """List helper should return brands sorted by name."""

    async with sqlite_session_factory() as session:
        service = BrandService(session)
        for name, domain in [("Raycast", "raycast.com"), ("Arc", "arc.net")]:
            await service.create_brand(
                BrandUpsertInput(
                    name=name,
                    domain=domain,
                    category="SaaS",
                    niche_ids=["tech"],
                    geo_markets=["US"],
                    consent_basis="public_business_contact",
                )
            )
        await session.commit()

    async with sqlite_session_factory() as session:
        service = BrandService(session)
        brands = await service.list_brands()
        ids = [brand.id for brand in brands]
        stored = list((await session.scalars(select(Brand).where(Brand.id.in_(ids)))).all())

    assert [brand.name for brand in brands] == ["Arc", "Raycast"]
    assert len(stored) == 2
