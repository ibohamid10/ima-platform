"""Tests for website, hiring, and branded-content enrichment."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import respx
from httpx import Response

from ima.brands.enricher import (
    BrandEnricher,
    BrandWebsiteAnalyzer,
    HiringSignalDetector,
    MetaAdLibraryService,
)
from ima.db.models import Brand
from ima.evidence.storage import LocalEvidenceStorage


@pytest.mark.asyncio()
async def test_brand_website_analyzer_detects_creator_program_and_contact(
    tmp_path: Path,
) -> None:
    """Website analyzer should extract creator-program signals and influencer emails."""

    analyzer = BrandWebsiteAnalyzer(storage=LocalEvidenceStorage(root=tmp_path))
    brand = Brand(
        name="Notion",
        domain="notion.so",
        niche_ids=["productivity"],
        geo_markets=["US"],
    )
    html = """
    <html>
      <body>
        <a href="/affiliate">Affiliate program</a>
        <a href="/creator-program">Creator Program</a>
        <p>Reach us via creators@notion.so</p>
      </body>
    </html>
    """

    with respx.mock(assert_all_called=True) as router:
        router.get("https://notion.so").mock(return_value=Response(200, text=html))
        result = await analyzer.analyze(
            brand,
            ["affiliate", "creator program", "partner program"],
        )

    assert result.creator_program_score == 1.0
    assert result.influencer_contact_email == "creators@notion.so"
    assert result.website_snapshot_uri is not None


@pytest.mark.asyncio()
async def test_brand_website_analyzer_returns_zero_without_signals(tmp_path: Path) -> None:
    """Website analyzer should return zero signals when keywords and emails are absent."""

    analyzer = BrandWebsiteAnalyzer(storage=LocalEvidenceStorage(root=tmp_path))
    brand = Brand(
        name="Unknown",
        domain="unknown.dev",
        niche_ids=["tech"],
        geo_markets=["US"],
    )
    html = "<html><body><p>Generic landing page.</p></body></html>"

    with respx.mock(assert_all_called=True) as router:
        router.get("https://unknown.dev").mock(return_value=Response(200, text=html))
        result = await analyzer.analyze(brand, ["affiliate", "creator program"])

    assert result.creator_program_score == 0.0
    assert result.contact_email is None


@pytest.mark.asyncio()
async def test_hiring_signal_detector_scores_recent_results() -> None:
    """Hiring detector should rate recent creator-partnership results highest."""

    detector = HiringSignalDetector()
    html = "Notion creator partnerships LinkedIn jobs posted 2 days ago"

    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.google.com/search").mock(return_value=Response(200, text=html))
        result = await detector.detect(
            brand_name="Notion",
            domain="notion.so",
            keywords=["creator partnerships", "influencer marketing"],
        )

    assert result.found is True
    assert result.score == 1.0
    assert result.freshness_hint == "recent"


@pytest.mark.asyncio()
async def test_meta_ad_library_service_uses_fallback_search_without_token() -> None:
    """Meta service should fall back to a search signal when no token is configured."""

    service = MetaAdLibraryService(access_token=None)

    with respx.mock(assert_all_called=True) as router:
        router.get("https://www.google.com/search").mock(
            return_value=Response(200, text='facebook.com/ads/library/?q=Notion ads/library')
        )
        result = await service.detect(
            Brand(
                name="Notion",
                domain="notion.so",
                niche_ids=["productivity"],
                geo_markets=["US"],
            )
        )

    assert result.source == "fallback_search"
    assert result.score == 0.5


@pytest.mark.asyncio()
async def test_brand_enricher_updates_brand_signals_in_place(
    sqlite_session_factory,
    tmp_path: Path,
) -> None:
    """Brand enricher should persist website, hiring, and branded-content signals."""

    async with sqlite_session_factory() as session:
        brand = Brand(
            name="Notion",
            domain="notion.so",
            niche_ids=["productivity"],
            geo_markets=["US"],
        )
        session.add(brand)
        await session.flush()

        enricher = BrandEnricher(
            session,
            website_analyzer=BrandWebsiteAnalyzer(
                storage=LocalEvidenceStorage(root=tmp_path)
            ),
            hiring_detector=HiringSignalDetector(),
            meta_service=MetaAdLibraryService(access_token=None),
        )
        with respx.mock(assert_all_called=True) as router:
            router.get("https://notion.so").mock(
                return_value=Response(
                    200,
                    text='<a href="/affiliate">Affiliate</a> creators@notion.so',
                )
            )
            router.get("https://www.google.com/search").mock(
                side_effect=[
                    Response(200, text="Notion influencer marketing job posted 3 days ago"),
                    Response(200, text='facebook.com/ads/library "Notion" ads/library'),
                ]
            )
            result = await enricher.enrich_brand(brand)
        await session.commit()

    assert result.creator_program_score == 0.6
    assert result.hiring_signal_score == 1.0
    assert result.branded_content_score == 0.5
    assert brand.creator_program_score == Decimal("0.6")
