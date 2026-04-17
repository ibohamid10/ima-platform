"""Source import pipeline connecting harvester fixtures to creator ingest."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from re import sub
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from ima.creators.ingest import CreatorIngestService
from ima.creators.schemas import CreatorIngestInput, CreatorIngestResult
from ima.db.session import get_session_factory
from ima.harvesters.fixture_harvester import CreatorEnricherStub, FixtureCreatorHarvester
from ima.harvesters.schemas import CreatorSourceImportResult, HarvestedCreatorRecord
from ima.temporal.client import get_temporal_client
from ima.temporal.constants import CREATOR_INGEST_WORKFLOW, CREATOR_TASK_QUEUE


class CreatorSourceWorkflowClient(Protocol):
    """Minimal protocol for executing creator ingest workflows."""

    async def execute_workflow(
        self,
        workflow: str,
        arg: CreatorIngestInput,
        *,
        id: str,
        task_queue: str,
        result_type: type[CreatorIngestResult],
        id_conflict_policy: WorkflowIDConflictPolicy,
    ) -> CreatorIngestResult:
        """Execute one workflow and return the typed creator ingest result."""


class CreatorSourceImportService:
    """Import fixture-based creator source batches into the canonical ingest flow."""

    def __init__(
        self,
        harvester: FixtureCreatorHarvester | None = None,
        enricher: CreatorEnricherStub | None = None,
        db_session_factory: async_sessionmaker[AsyncSession] | None = None,
        temporal_client_factory: (
            Callable[[], Awaitable[Client | CreatorSourceWorkflowClient]] | None
        ) = None,
    ) -> None:
        """Create the source import service with overridable local collaborators."""

        self.harvester = harvester or FixtureCreatorHarvester()
        self.enricher = enricher or CreatorEnricherStub()
        self.db_session_factory = db_session_factory or get_session_factory()
        self.temporal_client_factory = temporal_client_factory or get_temporal_client

    async def import_fixture_file(
        self,
        input_file: Path,
        *,
        via_temporal: bool = True,
        task_queue: str = CREATOR_TASK_QUEUE,
        workflow_prefix: str = "creator-source-import",
        workflow_run_token: str | None = None,
    ) -> CreatorSourceImportResult:
        """Load one fixture batch and send every record through canonical ingest."""

        batch = await self.harvester.harvest_from_file(input_file)
        return await self.import_records(
            batch.creators,
            batch_source=batch.source,
            batch_id=batch.batch_id,
            via_temporal=via_temporal,
            task_queue=task_queue,
            workflow_prefix=workflow_prefix,
            workflow_run_token=workflow_run_token,
        )

    async def import_records(
        self,
        records: list[HarvestedCreatorRecord],
        *,
        batch_source: str,
        batch_id: str | None = None,
        via_temporal: bool = True,
        task_queue: str = CREATOR_TASK_QUEUE,
        workflow_prefix: str = "creator-source-import",
        workflow_run_token: str | None = None,
    ) -> CreatorSourceImportResult:
        """Normalize harvested records and send them through canonical ingest."""

        payloads = [await self.enricher.enrich(record) for record in records]
        results: list[CreatorIngestResult] = []
        workflow_ids: list[str] = []

        if via_temporal:
            client = await self.temporal_client_factory()
            run_token = workflow_run_token or datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            for index, payload in enumerate(payloads, start=1):
                workflow_id = self._build_workflow_id(
                    prefix=workflow_prefix,
                    run_token=run_token,
                    payload=payload,
                    index=index,
                )
                result = await client.execute_workflow(
                    CREATOR_INGEST_WORKFLOW,
                    payload,
                    id=workflow_id,
                    task_queue=task_queue,
                    result_type=CreatorIngestResult,
                    id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
                )
                workflow_ids.append(workflow_id)
                results.append(result)
        else:
            for payload in payloads:
                async with self.db_session_factory() as session:
                    service = CreatorIngestService(session)
                    result = await service.ingest(payload)
                    await session.commit()
                    results.append(result)

        return CreatorSourceImportResult(
            batch_source=batch_source,
            batch_id=batch_id,
            total_records=len(records),
            imported_count=len(results),
            via_temporal=via_temporal,
            workflow_ids=workflow_ids,
            results=results,
        )

    def _build_workflow_id(
        self,
        *,
        prefix: str,
        run_token: str,
        payload: CreatorIngestInput,
        index: int,
    ) -> str:
        """Build a deterministic but collision-resistant workflow identifier."""

        normalized_prefix = self._slugify(prefix)
        normalized_platform = self._slugify(payload.platform)
        normalized_handle = self._slugify(payload.handle)
        return (
            f"{normalized_prefix}-{run_token}-{normalized_platform}-{normalized_handle}-{index:03d}"
        )

    def _slugify(self, value: str) -> str:
        """Normalize arbitrary text into a workflow-id-safe slug."""

        slug = sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
        return slug or "source"
