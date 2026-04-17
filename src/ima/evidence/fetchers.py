"""Fetchers for evidence-related HTML snapshots."""

from __future__ import annotations

from typing import Protocol

import httpx

from ima.config import settings


class EvidencePageFetcher(Protocol):
    """Protocol for fetching page HTML before artifact persistence."""

    async def fetch_html(self, url: str) -> str:
        """Fetch the HTML representation for one evidence page URL."""


class HttpEvidencePageFetcher:
    """HTTP-based page fetcher for profile and content HTML snapshots."""

    def __init__(
        self,
        timeout_seconds: float | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Create the HTTP fetcher with configurable timeout and user agent."""

        self.timeout_seconds = timeout_seconds or settings.evidence_fetch_timeout_seconds
        self.user_agent = user_agent or settings.evidence_fetch_user_agent

    async def fetch_html(self, url: str) -> str:
        """Fetch one URL and return the HTML text body."""

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
        ) as client:
            response = await client.get(url)
        response.raise_for_status()
        return response.text
