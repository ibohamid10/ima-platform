"""Tests for fixture-based harvester and source import pipeline behavior."""

from __future__ import annotations

from pathlib import Path

from ima.creators.schemas import CreatorIngestResult
from ima.harvesters.fixture_harvester import CreatorEnricherStub, FixtureCreatorHarvester
from ima.harvesters.pipeline import CreatorSourceImportService
from ima.harvesters.schemas import HarvestedCreatorRecord


class FakeWorkflowClient:
    """Capture workflow executions for source import tests."""

    def __init__(self) -> None:
        """Create the fake workflow client with an empty call log."""

        self.calls: list[dict[str, object]] = []

    async def execute_workflow(self, workflow: str, arg, **kwargs: object) -> CreatorIngestResult:
        """Record one workflow execution and return a deterministic result."""

        self.calls.append(
            {
                "workflow": workflow,
                "arg": arg,
                "kwargs": kwargs,
            }
        )
        return CreatorIngestResult(
            creator_id=f"creator-{len(self.calls)}",
            created=True,
            content_created=len(arg.content_items),
            content_updated=0,
            snapshot_recorded=arg.metric_snapshot is not None,
            score={
                "creator_id": f"creator-{len(self.calls)}",
                "growth_score": 0.7,
                "niche_fit_score": 0.5,
                "commercial_score": 0.8,
                "fraud_score": 0.2,
                "evidence_coverage_score": 0.8,
                "is_qualified": True,
                "qualification_reasons": [],
            },
        )


async def test_fixture_harvester_loads_batch() -> None:
    """The fixture harvester should parse the local source batch file."""

    harvester = FixtureCreatorHarvester()

    batch = await harvester.harvest_from_file(Path("tests/fixtures/creator_source_batch.json"))

    assert batch.source == "youtube_fixture"
    assert batch.batch_id == "yt-fixture-batch-001"
    assert len(batch.creators) == 2
    assert batch.creators[0].handle == "fixtureharvestone"


async def test_creator_enricher_stub_normalizes_source_record() -> None:
    """The enricher stub should convert harvested fields into the ingest schema."""

    batch = await FixtureCreatorHarvester().harvest_from_file(
        Path("tests/fixtures/creator_source_batch.json")
    )
    record = HarvestedCreatorRecord.model_validate(batch.creators[0].model_dump())

    payload = await CreatorEnricherStub().enrich(record)

    assert payload.handle == "fixtureharvestone"
    assert payload.metric_snapshot is not None
    assert "harvester:youtube_fixture" in payload.source_labels
    assert "enricher:stub" in payload.source_labels
    assert payload.content_items[0].platform_content_id == "yt-fixture-001"


async def test_source_import_service_direct_mode_persists_creators(
    sqlite_session_factory,
) -> None:
    """Direct mode should ingest fixture batch records through the canonical service."""

    service = CreatorSourceImportService(db_session_factory=sqlite_session_factory)

    result = await service.import_fixture_file(
        Path("tests/fixtures/creator_source_batch.json"),
        via_temporal=False,
    )

    assert result.total_records == 2
    assert result.imported_count == 2
    assert result.via_temporal is False
    assert len(result.results) == 2
    assert result.results[0].score.creator_id


async def test_source_import_service_temporal_mode_uses_ingest_workflow() -> None:
    """Temporal mode should route every normalized payload through the ingest workflow."""

    client = FakeWorkflowClient()

    async def fake_client_factory() -> FakeWorkflowClient:
        """Return the fake workflow client for test isolation."""

        return client

    service = CreatorSourceImportService(temporal_client_factory=fake_client_factory)

    result = await service.import_fixture_file(
        Path("tests/fixtures/creator_source_batch.json"),
        via_temporal=True,
        workflow_prefix="fixture-batch",
        workflow_run_token="testrun",
    )

    assert result.via_temporal is True
    assert result.imported_count == 2
    assert len(result.workflow_ids) == 2
    assert result.workflow_ids[0] == "fixture-batch-testrun-youtube-fixtureharvestone-001"
    assert client.calls[0]["workflow"] == "creator-ingest-workflow"
