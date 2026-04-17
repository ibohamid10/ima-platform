"""Temporal activities for creator ingest and scoring flows."""

from __future__ import annotations

from temporalio import activity

from ima.creators.ingest import CreatorIngestService
from ima.creators.schemas import CreatorIngestInput, CreatorIngestResult
from ima.db.session import get_session_factory
from ima.logging import get_logger
from ima.temporal.constants import CREATOR_INGEST_ACTIVITY

logger = get_logger(__name__)


async def execute_creator_ingest(payload: CreatorIngestInput) -> CreatorIngestResult:
    """Execute creator ingest inside one database session."""

    async with get_session_factory()() as session:
        service = CreatorIngestService(session)
        result = await service.ingest(payload)
        await session.commit()
        return result


@activity.defn(name=CREATOR_INGEST_ACTIVITY)
async def creator_ingest_activity(payload: CreatorIngestInput) -> CreatorIngestResult:
    """Temporal activity wrapper around the creator ingest service."""

    info = activity.info()
    logger.info(
        "creator_ingest_activity_started",
        workflow_id=info.workflow_id,
        activity_id=info.activity_id,
        creator_handle=payload.handle,
        platform=payload.platform,
    )
    result = await execute_creator_ingest(payload)
    logger.info(
        "creator_ingest_activity_completed",
        workflow_id=info.workflow_id,
        activity_id=info.activity_id,
        creator_id=result.creator_id,
        created=result.created,
        content_created=result.content_created,
        content_updated=result.content_updated,
    )
    return result
