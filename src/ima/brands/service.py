"""Brand CRUD service and typed payloads."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ima.db.models import Brand


class BrandUpsertInput(BaseModel):
    """Structured input for creating or updating a brand."""

    name: str
    domain: str
    category: str | None = None
    niche_ids: list[str] = Field(default_factory=list)
    geo_markets: list[str] = Field(default_factory=list)
    consent_basis: str | None = None


class BrandResult(BaseModel):
    """Serializable brand representation for CLI and tests."""

    id: str
    name: str
    domain: str
    category: str | None = None
    niche_ids: list[str]
    geo_markets: list[str]
    spend_intent_score: float | None = None
    creator_program_score: float | None = None
    hiring_signal_score: float | None = None
    branded_content_score: float | None = None
    contact_email: str | None = None
    influencer_contact_email: str | None = None
    contact_confidence: float | None = None
    website_snapshot_uri: str | None = None
    consent_basis: str | None = None


class BrandService:
    """CRUD helpers for the brand-side domain model."""

    def __init__(self, session: AsyncSession) -> None:
        """Create a brand service for one async session."""

        self.session = session

    async def get_by_domain(self, domain: str) -> Brand | None:
        """Load one brand by canonical domain."""

        statement = select(Brand).where(Brand.domain == self._normalize_domain(domain))
        return await self.session.scalar(statement)

    async def list_brands(self) -> list[Brand]:
        """Return all brands ordered by name."""

        return list((await self.session.scalars(select(Brand).order_by(Brand.name.asc()))).all())

    async def create_brand(self, payload: BrandUpsertInput) -> Brand:
        """Create one brand and persist it."""

        brand = Brand(
            name=payload.name.strip(),
            domain=self._normalize_domain(payload.domain),
            category=payload.category,
            niche_ids=sorted(set(payload.niche_ids)),
            geo_markets=sorted(set(payload.geo_markets)),
            consent_basis=payload.consent_basis,
            last_seen_at=datetime.now(UTC),
        )
        self.session.add(brand)
        await self.session.flush()
        return brand

    async def update_brand(self, brand: Brand, payload: BrandUpsertInput) -> Brand:
        """Apply an update payload onto an existing brand."""

        brand.name = payload.name.strip()
        brand.domain = self._normalize_domain(payload.domain)
        brand.category = payload.category
        brand.niche_ids = sorted(set(payload.niche_ids))
        brand.geo_markets = sorted(set(payload.geo_markets))
        brand.consent_basis = payload.consent_basis or brand.consent_basis
        brand.last_seen_at = datetime.now(UTC)
        await self.session.flush()
        return brand

    async def upsert_brand(self, payload: BrandUpsertInput) -> tuple[Brand, bool]:
        """Create or update one brand by unique domain."""

        brand = await self.get_by_domain(payload.domain)
        created = brand is None
        if brand is None:
            brand = await self.create_brand(payload)
        else:
            brand = await self.update_brand(brand, payload)
        return brand, created

    def to_result(self, brand: Brand) -> BrandResult:
        """Convert one ORM object into a serializable result."""

        return BrandResult(
            id=str(brand.id),
            name=brand.name,
            domain=brand.domain,
            category=brand.category,
            niche_ids=list(brand.niche_ids),
            geo_markets=list(brand.geo_markets),
            spend_intent_score=(
                float(brand.spend_intent_score)
                if brand.spend_intent_score is not None
                else None
            ),
            creator_program_score=(
                float(brand.creator_program_score)
                if brand.creator_program_score is not None
                else None
            ),
            hiring_signal_score=(
                float(brand.hiring_signal_score)
                if brand.hiring_signal_score is not None
                else None
            ),
            branded_content_score=(
                float(brand.branded_content_score)
                if brand.branded_content_score is not None
                else None
            ),
            contact_email=brand.contact_email,
            influencer_contact_email=brand.influencer_contact_email,
            contact_confidence=(
                float(brand.contact_confidence) if brand.contact_confidence is not None else None
            ),
            website_snapshot_uri=brand.website_snapshot_uri,
            consent_basis=brand.consent_basis,
        )

    def _normalize_domain(self, value: str) -> str:
        """Normalize a domain-like string into a stable lowercase identifier."""

        return value.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
