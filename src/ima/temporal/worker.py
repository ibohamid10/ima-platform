"""Temporal worker helpers for running local workflow workers."""

from __future__ import annotations

from temporalio.worker import Worker

from ima.temporal.activities import creator_ingest_activity
from ima.temporal.client import get_temporal_client
from ima.temporal.constants import CREATOR_TASK_QUEUE
from ima.temporal.workflows import CreatorIngestWorkflow


async def run_creator_worker(task_queue: str = CREATOR_TASK_QUEUE) -> None:
    """Run the local Temporal worker for creator ingest workflows."""

    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[CreatorIngestWorkflow],
        activities=[creator_ingest_activity],
    )
    await worker.run()
