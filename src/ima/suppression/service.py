"""Suppression lookup service across all five suppression tables."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ima.db.models import (
    SuppressionHardBounce,
    SuppressionManual,
    SuppressionSpamComplaint,
    SuppressionUnsubscribe,
    SuppressionWrongPerson,
)


class SuppressionService:
    """Check whether an email is blocked for any suppression reason."""

    def __init__(self, session: AsyncSession) -> None:
        """Create the suppression service for one async session."""

        self.session = session

    async def is_suppressed(self, email: str) -> bool:
        """Return whether the email exists in any suppression table."""

        normalized = email.strip().lower()
        statements = [
            select(model.id).where(or_(model.email == normalized, model.email == email.strip()))
            for model in (
                SuppressionUnsubscribe,
                SuppressionHardBounce,
                SuppressionSpamComplaint,
                SuppressionWrongPerson,
                SuppressionManual,
            )
        ]
        for statement in statements:
            if await self.session.scalar(statement) is not None:
                return True
        return False
