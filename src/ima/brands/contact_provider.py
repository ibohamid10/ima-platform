"""Contact provider protocol and a Hunter.io-backed stub adapter."""

from __future__ import annotations

from typing import Protocol

import httpx
from pydantic import BaseModel

from ima.config import settings


class ContactResult(BaseModel):
    """One discovered contact candidate for a brand domain."""

    email: str
    full_name: str | None = None
    title: str | None = None
    confidence: float = 0.0
    source: str = "unknown"


class EmailVerificationResult(BaseModel):
    """Structured email verification result."""

    email: str
    is_deliverable: bool
    confidence: float = 0.0
    status: str = "unknown"


class ContactProvider(Protocol):
    """Protocol for contact-enrichment adapters."""

    provider_name: str

    async def find_contacts(self, domain: str, role_keywords: list[str]) -> list[ContactResult]:
        """Find relevant contacts for a given domain."""

    async def verify_email(self, email: str) -> EmailVerificationResult:
        """Verify deliverability and confidence for one email."""


class HunterAdapter:
    """Hunter.io adapter activated once API access is available."""

    provider_name = "hunter"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.hunter.io/v2",
        timeout_seconds: float = 15.0,
    ) -> None:
        """Create the adapter with optional explicit credentials."""

        self.api_key = api_key if api_key is not None else settings.hunter_api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    async def find_contacts(self, domain: str, role_keywords: list[str]) -> list[ContactResult]:
        """Return contacts ranked by Hunter confidence and role keyword overlap."""

        self._require_api_key()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.get(
                "/domain-search",
                params={"domain": domain, "api_key": self.api_key},
            )
            response.raise_for_status()
            payload = response.json()

        keyword_hits = tuple(keyword.lower() for keyword in role_keywords if keyword.strip())
        contacts: list[ContactResult] = []
        for item in payload.get("data", {}).get("emails", []):
            position = str(item.get("position") or "").lower()
            if keyword_hits and not any(keyword in position for keyword in keyword_hits):
                continue
            contacts.append(
                ContactResult(
                    email=str(item.get("value")),
                    full_name=item.get("first_name"),
                    title=item.get("position"),
                    confidence=float(item.get("confidence") or 0) / 100.0,
                    source=self.provider_name,
                )
            )
        return contacts

    async def verify_email(self, email: str) -> EmailVerificationResult:
        """Verify one email via Hunter's email-verifier endpoint."""

        self._require_api_key()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.get(
                "/email-verifier",
                params={"email": email, "api_key": self.api_key},
            )
            response.raise_for_status()
            payload = response.json()

        data = payload.get("data", {})
        status = str(data.get("status") or "unknown")
        score = float(data.get("score") or 0)
        return EmailVerificationResult(
            email=email,
            is_deliverable=status in {"valid", "accept_all"},
            confidence=score / 100.0 if score > 1 else score,
            status=status,
        )

    def _require_api_key(self) -> None:
        """Fail clearly until the Hunter integration is explicitly activated."""

        if not self.api_key:
            raise NotImplementedError(
                "HunterAdapter ist vorbereitet, aber noch nicht aktiviert. "
                "Setze HUNTER_API_KEY, sobald der Hunter.io Account steht."
            )
