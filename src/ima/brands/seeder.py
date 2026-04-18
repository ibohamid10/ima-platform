"""YAML-backed brand seeding helpers."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ima.brands.service import BrandService, BrandUpsertInput


class BrandSeedRecord(BaseModel):
    """One YAML seed record for a brand."""

    name: str
    domain: str
    category: str | None = None
    niche_ids: list[str] = Field(default_factory=list)
    geo_markets: list[str] = Field(default_factory=list)


class BrandSeedResult(BaseModel):
    """Summary of one brand-seed import."""

    file_path: str
    total_records: int
    created_count: int
    updated_count: int
    domains: list[str]


class BrandSeeder:
    """Import brands from YAML into the canonical brand service."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a seeder for one async session."""

        self.session = session
        self.service = BrandService(session)

    async def seed_file(self, file_path: Path) -> BrandSeedResult:
        """Read and import one YAML seed file."""

        raw_records = yaml.safe_load(file_path.read_text(encoding="utf-8")) or []
        records = [BrandSeedRecord.model_validate(item) for item in raw_records]
        created_count = 0
        updated_count = 0
        domains: list[str] = []

        for record in records:
            _, created = await self.service.upsert_brand(
                BrandUpsertInput(
                    name=record.name,
                    domain=record.domain,
                    category=record.category,
                    niche_ids=record.niche_ids,
                    geo_markets=record.geo_markets,
                    consent_basis="public_business_contact",
                )
            )
            domains.append(record.domain)
            if created:
                created_count += 1
            else:
                updated_count += 1

        await self.session.flush()
        return BrandSeedResult(
            file_path=str(file_path),
            total_records=len(records),
            created_count=created_count,
            updated_count=updated_count,
            domains=domains,
        )
