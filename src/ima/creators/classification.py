"""Creator classification helpers that persist classifier output into creators."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ima.agents.classifier.contract import CLASSIFIER_CONTRACT, ClassifierInput, ClassifierOutput
from ima.agents.executor import AgentExecutor
from ima.db.models import Creator, CreatorContent


class CreatorClassificationService:
    """Run the classifier agent and persist niche labels onto creators."""

    def __init__(
        self,
        session: AsyncSession,
        llm_providers: dict[str, object],
        db_session_factory: async_sessionmaker,
        langfuse_hook: object,
    ) -> None:
        """Create the classification service for one creator session."""

        self.session = session
        self.executor = AgentExecutor(
            contract=CLASSIFIER_CONTRACT,
            llm_providers=llm_providers,
            db_session_factory=db_session_factory,
            langfuse_hook=langfuse_hook,
        )

    async def classify_creator_by_handle(self, *, platform: str, handle: str) -> ClassifierOutput:
        """Classify one creator by platform and handle and persist the result."""

        creator = await self.session.scalar(
            select(Creator).where(Creator.platform == platform, Creator.handle == handle)
        )
        if creator is None:
            raise ValueError(f"Creator {platform}/{handle} wurde nicht gefunden.")

        content_items = list(
            (
                await self.session.scalars(
                    select(CreatorContent)
                    .where(CreatorContent.creator_id == creator.id)
                    .order_by(CreatorContent.published_at.desc().nullslast())
                    .limit(5)
                )
            ).all()
        )
        captions = [item.caption for item in content_items if item.caption][:5]
        hashtags = []
        for item in content_items:
            hashtags.extend(item.hashtags)

        output = await self.executor.run(
            ClassifierInput(
                creator_handle=creator.handle,
                platform=creator.platform,
                bio=creator.bio or "",
                recent_captions=captions,
                top_hashtags=hashtags[:10],
            )
        )
        if not isinstance(output, ClassifierOutput):
            raise TypeError("Classifier output ist nicht vom erwarteten Typ.")

        creator.niche_labels = sorted(set([output.niche, *output.sub_niches]))
        creator.language = output.language
        await self.session.flush()
        return output
