"""Tests for YAML-based brand seeding."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from ima.brands.seeder import BrandSeeder
from ima.db.models import Brand


@pytest.mark.asyncio()
async def test_brand_seeder_imports_yaml_records(sqlite_session_factory, tmp_path: Path) -> None:
    """Seeder should import multiple brands from one YAML file."""

    seed_file = tmp_path / "brands.yaml"
    seed_file.write_text(
        """
- name: Notion
  domain: notion.so
  category: SaaS
  niche_ids: [productivity, tech]
  geo_markets: [US, DE]
- name: Raycast
  domain: raycast.com
  category: SaaS
  niche_ids: [tech]
  geo_markets: [US, GB]
""".strip(),
        encoding="utf-8",
    )

    async with sqlite_session_factory() as session:
        result = await BrandSeeder(session).seed_file(seed_file)
        await session.commit()

    async with sqlite_session_factory() as session:
        brands = list((await session.scalars(select(Brand).order_by(Brand.domain.asc()))).all())

    assert result.total_records == 2
    assert result.created_count == 2
    assert [brand.domain for brand in brands] == ["notion.so", "raycast.com"]
    assert all(brand.consent_basis == "public_business_contact" for brand in brands)


@pytest.mark.asyncio()
async def test_brand_seeder_updates_existing_domain(sqlite_session_factory, tmp_path: Path) -> None:
    """Seeder should upsert existing brands by domain."""

    seed_file = tmp_path / "brands.yaml"
    seed_file.write_text(
        """
- name: Notion
  domain: notion.so
  category: SaaS
  niche_ids: [productivity]
  geo_markets: [US]
""".strip(),
        encoding="utf-8",
    )

    async with sqlite_session_factory() as session:
        seeder = BrandSeeder(session)
        await seeder.seed_file(seed_file)
        await session.commit()

    seed_file.write_text(
        """
- name: Notion Labs
  domain: notion.so
  category: Productivity Software
  niche_ids: [productivity, tech]
  geo_markets: [US, DE]
""".strip(),
        encoding="utf-8",
    )

    async with sqlite_session_factory() as session:
        result = await BrandSeeder(session).seed_file(seed_file)
        await session.commit()
        brand = await session.scalar(select(Brand).where(Brand.domain == "notion.so"))

    assert result.created_count == 0
    assert result.updated_count == 1
    assert brand is not None
    assert brand.name == "Notion Labs"
    assert brand.niche_ids == ["productivity", "tech"]
