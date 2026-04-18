"""Brand website, hiring, and branded-content signal enrichment."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ima.config import settings
from ima.db.models import Brand
from ima.evidence.storage import EvidenceStorage, LocalEvidenceStorage
from ima.logging import get_logger
from ima.niches import NicheRegistry, get_niche_registry

logger = get_logger(__name__)

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
LINK_RE = re.compile(r"""href=["']([^"'#>]+)["']""", re.IGNORECASE)


class WebsiteSignalResult(BaseModel):
    """Signals extracted from a brand website."""

    domain: str
    creator_program_score: float = 0.0
    contact_email: str | None = None
    influencer_contact_email: str | None = None
    contact_confidence: float = 0.0
    website_snapshot_uri: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)


class HiringSignalResult(BaseModel):
    """Hiring signal derived from a web search."""

    domain: str
    score: float = 0.0
    found: bool = False
    freshness_hint: str | None = None


class BrandedContentSignalResult(BaseModel):
    """Meta Ad Library or fallback branded-content signal."""

    domain: str
    score: float = 0.0
    active_ads_found: int = 0
    source: str = "fallback"


class BrandEnrichmentResult(BaseModel):
    """Combined brand enrichment output."""

    brand_id: str
    domain: str
    creator_program_score: float
    hiring_signal_score: float
    branded_content_score: float
    spend_intent_score: float | None = None
    influencer_contact_email: str | None = None
    website_snapshot_uri: str | None = None


class BrandWebsiteAnalyzer:
    """HTML-based website analyzer for creator-program and contact signals."""

    def __init__(
        self,
        storage: EvidenceStorage | None = None,
        timeout_seconds: float = 15.0,
        user_agent: str | None = None,
    ) -> None:
        """Create the analyzer with shared storage and HTTP defaults."""

        self.storage = storage or LocalEvidenceStorage()
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent or settings.evidence_fetch_user_agent

    async def analyze(self, brand: Brand, niche_keywords: list[str]) -> WebsiteSignalResult:
        """Fetch a homepage, persist a snapshot, and derive website signals."""

        url = self._homepage_url(brand.domain)
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        stored = await self.storage.put_text(
            key=f"brands/{brand.domain}/website/homepage.html",
            payload=html,
            content_type="text/html",
        )

        keyword_hits = self._keyword_hits(html=html, keywords=niche_keywords)
        creator_program_score = 0.0
        if len(keyword_hits) >= 2:
            creator_program_score = 1.0
        elif keyword_hits:
            creator_program_score = 0.6

        emails = EMAIL_RE.findall(html)
        influencer_email = self._pick_specialized_email(
            emails,
            preferred_prefixes=("influencer", "partnership", "creators", "collab", "affiliate"),
        )
        contact_email = influencer_email or self._pick_specialized_email(
            emails,
            preferred_prefixes=("hello", "contact", "team", "support"),
        )
        contact_confidence = 0.9 if influencer_email else 0.65 if contact_email else 0.0

        return WebsiteSignalResult(
            domain=brand.domain,
            creator_program_score=creator_program_score,
            contact_email=contact_email,
            influencer_contact_email=influencer_email,
            contact_confidence=contact_confidence,
            website_snapshot_uri=stored.source_uri,
            matched_keywords=keyword_hits,
        )

    def _homepage_url(self, domain: str) -> str:
        """Build an HTTPS homepage URL from a bare domain."""

        return f"https://{domain}"

    def _keyword_hits(self, *, html: str, keywords: list[str]) -> list[str]:
        """Return creator-program keyword hits from text and links."""

        normalized = html.lower()
        links = [match.lower() for match in LINK_RE.findall(html)]
        hits: list[str] = []
        for keyword in keywords:
            normalized_keyword = keyword.lower()
            if normalized_keyword in normalized or any(
                normalized_keyword in link for link in links
            ):
                hits.append(normalized_keyword)
        return sorted(set(hits))

    def _pick_specialized_email(
        self,
        emails: list[str],
        *,
        preferred_prefixes: tuple[str, ...],
    ) -> str | None:
        """Pick the most relevant email address by local-part prefix."""

        for email in emails:
            local_part = email.split("@", maxsplit=1)[0].lower()
            if any(local_part.startswith(prefix) for prefix in preferred_prefixes):
                return email.lower()
        return emails[0].lower() if emails else None


class HiringSignalDetector:
    """Simple search-based hiring signal detector."""

    def __init__(self, timeout_seconds: float = 15.0) -> None:
        """Create the detector with HTTP defaults."""

        self.timeout_seconds = timeout_seconds

    async def detect(self, brand_name: str, domain: str, keywords: list[str]) -> HiringSignalResult:
        """Search for creator-partnership hiring signals."""

        quoted_keywords = " OR ".join(f'"{keyword}"' for keyword in keywords)
        query = f'site:linkedin.com/jobs "{brand_name}" ({quoted_keywords})'
        html = await self._fetch_search_page(query)
        normalized = html.lower()
        found = brand_name.lower() in normalized and any(
            keyword.lower() in normalized for keyword in keywords
        )
        freshness_hint = None
        score = 0.0
        recent_markers = ("hours ago", "days ago", "gestern", "heute")
        stale_markers = ("weeks ago", "months ago", "vor", "tage")
        if found:
            if any(marker in normalized for marker in recent_markers):
                score = 1.0
                freshness_hint = "recent"
            elif any(marker in normalized for marker in stale_markers):
                score = 0.5
                freshness_hint = "stale"
            else:
                score = 0.5
                freshness_hint = "unknown"
        return HiringSignalResult(
            domain=domain,
            score=score,
            found=found,
            freshness_hint=freshness_hint,
        )

    async def _fetch_search_page(self, query: str) -> str:
        """Fetch a Google search result page or return an empty signal on failure."""

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": settings.evidence_fetch_user_agent},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    "https://www.google.com/search",
                    params={"q": query, "hl": "en"},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(
                    "brand_hiring_signal_search_failed",
                    query=query,
                    error_message=str(exc),
                )
                return ""
        return response.text


class MetaAdLibraryService:
    """Best-effort branded-content check via Meta API with a search fallback."""

    def __init__(self, access_token: str | None = None, timeout_seconds: float = 15.0) -> None:
        """Create the service with optional token-based API access."""

        self.access_token = (
            access_token if access_token is not None else settings.meta_access_token
        )
        self.timeout_seconds = timeout_seconds

    async def detect(self, brand: Brand) -> BrandedContentSignalResult:
        """Return a branded-content signal from the API or a fallback search."""

        if self.access_token:
            api_result = await self._detect_via_api(brand)
            if api_result is not None:
                return api_result

        fallback_score = await self._detect_via_fallback_search(brand.name)
        return BrandedContentSignalResult(
            domain=brand.domain,
            score=fallback_score,
            active_ads_found=1 if fallback_score > 0 else 0,
            source="fallback_search",
        )

    async def _detect_via_api(self, brand: Brand) -> BrandedContentSignalResult | None:
        """Query the Graph API when a token is configured."""

        async with httpx.AsyncClient(
            base_url=settings.meta_graph_api_base_url,
            timeout=self.timeout_seconds,
        ) as client:
            try:
                response = await client.get(
                    "/ads_archive",
                    params={
                        "access_token": self.access_token,
                        "search_terms": brand.name,
                        "ad_type": "ALL",
                        "ad_reached_countries": '["US"]',
                        "fields": (
                            "page_name,ad_creation_time,"
                            "ad_delivery_start_time,ad_delivery_stop_time"
                        ),
                        "limit": 10,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(
                    "meta_ad_library_unavailable",
                    brand=brand.domain,
                    error_message=str(exc),
                )
                return None

        payload = response.json()
        data = payload.get("data", [])
        if not data:
            return BrandedContentSignalResult(
                domain=brand.domain,
                score=0.0,
                active_ads_found=0,
                source="meta_api",
            )

        active_ads = len(data)
        score = min(1.0, 0.3 + (active_ads * 0.15))
        return BrandedContentSignalResult(
            domain=brand.domain,
            score=round(score, 4),
            active_ads_found=active_ads,
            source="meta_api",
        )

    async def _detect_via_fallback_search(self, brand_name: str) -> float:
        """Fallback search that avoids blocking spend-intent on Meta access."""

        query = f'site:facebook.com/ads/library "{brand_name}"'
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            headers={"User-Agent": settings.evidence_fetch_user_agent},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    "https://www.google.com/search",
                    params={"q": query, "hl": "en"},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(
                    "meta_ad_library_fallback_search_failed",
                    brand_name=brand_name,
                    error_message=str(exc),
                )
                return 0.0

        normalized = response.text.lower()
        return 0.5 if "ads/library" in normalized and brand_name.lower() in normalized else 0.0


class BrandEnricher:
    """Enrich stored brands with website, hiring, and branded-content signals."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        niche_registry: NicheRegistry | None = None,
        website_analyzer: BrandWebsiteAnalyzer | None = None,
        hiring_detector: HiringSignalDetector | None = None,
        meta_service: MetaAdLibraryService | None = None,
    ) -> None:
        """Create the orchestrating brand enricher."""

        self.session = session
        self.niche_registry = niche_registry or get_niche_registry()
        self.website_analyzer = website_analyzer or BrandWebsiteAnalyzer()
        self.hiring_detector = hiring_detector or HiringSignalDetector()
        self.meta_service = meta_service or MetaAdLibraryService()

    async def enrich_brand(self, brand: Brand) -> BrandEnrichmentResult:
        """Enrich one brand record in place."""

        creator_keywords = self._creator_program_keywords(brand.niche_ids)
        hiring_keywords = self._hiring_keywords(brand.niche_ids)
        website_result = await self.website_analyzer.analyze(brand, creator_keywords)
        hiring_result = await self.hiring_detector.detect(
            brand.name,
            brand.domain,
            hiring_keywords,
        )
        branded_result = await self.meta_service.detect(brand)

        brand.creator_program_score = Decimal(str(website_result.creator_program_score))
        brand.contact_email = website_result.contact_email
        brand.influencer_contact_email = website_result.influencer_contact_email
        brand.contact_confidence = Decimal(str(website_result.contact_confidence))
        brand.website_snapshot_uri = website_result.website_snapshot_uri
        brand.hiring_signal_score = Decimal(str(hiring_result.score))
        brand.branded_content_score = Decimal(str(branded_result.score))
        brand.last_seen_at = datetime.now(UTC)
        await self.session.flush()

        return BrandEnrichmentResult(
            brand_id=str(brand.id),
            domain=brand.domain,
            creator_program_score=website_result.creator_program_score,
            hiring_signal_score=hiring_result.score,
            branded_content_score=branded_result.score,
            influencer_contact_email=website_result.influencer_contact_email,
            website_snapshot_uri=website_result.website_snapshot_uri,
        )

    async def enrich_all(self) -> list[BrandEnrichmentResult]:
        """Enrich every stored brand in name order."""

        brands = list(
            (await self.session.scalars(select(Brand).order_by(Brand.name.asc()))).all()
        )
        return [await self.enrich_brand(brand) for brand in brands]

    def _creator_program_keywords(self, niche_ids: list[str]) -> list[str]:
        """Collect creator-program keywords across all associated niches."""

        keywords = {
            keyword.lower()
            for niche_id in niche_ids
            if self.niche_registry.has(niche_id)
            for keyword in self.niche_registry.get(
                niche_id
            ).brand_signals.keywords_creator_programs
        }
        return sorted(keywords) or [
            "affiliate",
            "ambassador",
            "creator program",
            "partner program",
            "collab",
        ]

    def _hiring_keywords(self, niche_ids: list[str]) -> list[str]:
        """Collect hiring keywords across all associated niches."""

        keywords = {
            keyword.lower()
            for niche_id in niche_ids
            if self.niche_registry.has(niche_id)
            for keyword in self.niche_registry.get(niche_id).brand_signals.keywords_hiring
        }
        return sorted(keywords) or [
            "influencer marketing",
            "creator partnerships",
            "content partnerships",
        ]
