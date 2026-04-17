"""Temporal workflows for creator ingest orchestration."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from ima.creators.schemas import CreatorIngestInput, CreatorIngestResult
from ima.temporal.constants import (
    CREATOR_INGEST_ACTIVITY,
    CREATOR_INGEST_WORKFLOW,
    CREATOR_TASK_QUEUE,
)


@workflow.defn(name=CREATOR_INGEST_WORKFLOW)
class CreatorIngestWorkflow:
    """Minimal Temporal workflow for one creator ingest and re-score run."""

    @workflow.run
    async def run(self, payload: CreatorIngestInput) -> CreatorIngestResult:
        """Execute one creator ingest activity with bounded retries."""

        # DECISION: DECISIONS.md#2026-04-16---temporal-als-workflow-engine
        # DECISION:
        # DECISIONS.md#2026-04-16---temporal-workflows-importieren-nur-sandbox-sichere-contracts
        return await workflow.execute_activity(
            CREATOR_INGEST_ACTIVITY,
            payload,
            task_queue=CREATOR_TASK_QUEUE,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
            result_type=CreatorIngestResult,
            summary=f"creator_ingest:{payload.platform}/{payload.handle}",
        )
