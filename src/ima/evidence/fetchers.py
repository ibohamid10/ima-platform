"""Fetchers for evidence-related HTML snapshots and visual captures."""

from __future__ import annotations

from typing import Protocol

import httpx

from ima.config import settings


class EvidencePageFetcher(Protocol):
    """Protocol for fetching page HTML before artifact persistence."""

    async def fetch_html(self, url: str) -> str:
        """Fetch the HTML representation for one evidence page URL."""


class EvidenceVisualFetcher(Protocol):
    """Protocol for capturing a visual snapshot of one page URL."""

    async def capture_png(self, url: str) -> bytes:
        """Capture one page as a PNG image and return the raw bytes."""


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


class PlaywrightScreenshotFetcher:
    """Browser-based page screenshot fetcher using Playwright."""

    def __init__(
        self,
        timeout_seconds: float | None = None,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Create the screenshot fetcher with configurable browser settings."""

        self.timeout_milliseconds = int(
            1000 * (timeout_seconds or settings.evidence_screenshot_timeout_seconds)
        )
        self.viewport_width = viewport_width or settings.evidence_screenshot_viewport_width
        self.viewport_height = viewport_height or settings.evidence_screenshot_viewport_height
        self.user_agent = user_agent or settings.evidence_fetch_user_agent

    async def capture_png(self, url: str) -> bytes:
        """Capture one page URL as a full-page PNG screenshot."""

        try:
            from playwright.async_api import Error as PlaywrightError
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright ist nicht installiert. "
                "Bitte Dependencies und Browser-Binaries einrichten."
            ) from exc

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={
                        "width": self.viewport_width,
                        "height": self.viewport_height,
                    },
                    user_agent=self.user_agent,
                )
                page = await context.new_page()
                try:
                    response = await page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=self.timeout_milliseconds,
                    )
                    if response is not None and response.status >= 400:
                        raise RuntimeError(
                            f"Screenshot page returned HTTP {response.status} for {url}"
                        )
                    return await page.screenshot(type="png", full_page=True)
                finally:
                    await context.close()
                    await browser.close()
        except PlaywrightError as exc:
            raise RuntimeError(f"Playwright screenshot failed for {url}: {exc}") from exc
