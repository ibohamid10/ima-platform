"""Tests for the global suppression lookup service."""

from __future__ import annotations

import pytest

from ima.db.models import (
    SuppressionHardBounce,
    SuppressionManual,
    SuppressionSpamComplaint,
    SuppressionUnsubscribe,
    SuppressionWrongPerson,
)
from ima.suppression.service import SuppressionService


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("model_cls", "email"),
    [
        (SuppressionUnsubscribe, "unsub@example.com"),
        (SuppressionHardBounce, "bounce@example.com"),
        (SuppressionSpamComplaint, "spam@example.com"),
        (SuppressionWrongPerson, "wrong@example.com"),
        (SuppressionManual, "manual@example.com"),
    ],
)
async def test_suppression_service_detects_all_reasons(
    sqlite_session_factory,
    model_cls,
    email: str,
) -> None:
    """Every suppression table should trigger the pre-send guard."""

    async with sqlite_session_factory() as session:
        session.add(model_cls(email=email, entity_type="brand_contact", reason="blocked"))
        await session.commit()

    async with sqlite_session_factory() as session:
        service = SuppressionService(session)
        assert await service.is_suppressed(email) is True


@pytest.mark.asyncio()
async def test_suppression_service_returns_false_for_unsuppressed_email(
    sqlite_session_factory,
) -> None:
    """Emails not present in any table should pass the suppression check."""

    async with sqlite_session_factory() as session:
        service = SuppressionService(session)
        assert await service.is_suppressed("clear@example.com") is False
