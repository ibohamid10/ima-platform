"""Database model tests for week-2 creator tables."""

from __future__ import annotations

from sqlalchemy import select

from ima.db.models import (
    ConsentStatus,
    Creator,
    CreatorContent,
    CreatorContentType,
    CreatorPlatform,
)


async def test_creator_and_content_relationship(sqlite_session_factory) -> None:
    """Creator content should persist and load through the ORM relationship."""

    async with sqlite_session_factory() as session:
        creator = Creator(
            platform=CreatorPlatform.YOUTUBE.value,
            handle="fitnessfranz",
            profile_url="https://youtube.com/@fitnessfranz",
            bio="Hyrox Athlet aus Wien",
            followers=125000,
            consent_basis=ConsentStatus.LEGITIMATE_INTEREST.value,
            source_labels=["youtube_api"],
        )
        creator.content_items.append(
            CreatorContent(
                content_type=CreatorContentType.VIDEO.value,
                platform_content_id="yt-123",
                title="Hyrox PR in Wien",
                caption="Neue Bestzeit im Training.",
                hashtags=["hyrox", "fitness", "wien"],
                raw_payload={"source": "fixture"},
            )
        )
        session.add(creator)
        await session.commit()

    async with sqlite_session_factory() as session:
        stored_creator = await session.scalar(
            select(Creator).where(Creator.handle == "fitnessfranz")
        )

    assert stored_creator is not None
    assert stored_creator.platform == CreatorPlatform.YOUTUBE.value
    assert stored_creator.consent_basis == ConsentStatus.LEGITIMATE_INTEREST.value
    assert len(stored_creator.content_items) == 1
    assert stored_creator.content_items[0].content_type == CreatorContentType.VIDEO.value
