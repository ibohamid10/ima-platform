"""Tests for Temporal creator activities and workflow orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from temporalio.common import RetryPolicy

from ima.creators.schemas import (
    CreatorIngestInput,
    CreatorIngestResult,
    CreatorMetricSnapshotPayload,
)
from ima.temporal.activities import execute_creator_ingest
from ima.temporal.constants import CREATOR_INGEST_ACTIVITY, CREATOR_TASK_QUEUE
from ima.temporal.workflows import CreatorIngestWorkflow


def _ingest_payload() -> CreatorIngestInput:
    """Return a small but valid creator ingest payload for Temporal tests."""

    return CreatorIngestInput(
        platform="youtube",
        handle="temporalfixture",
        profile_url="https://youtube.com/@temporalfixture",
        bio="Hyrox coach and nutrition creator from Vienna.",
        follower_count=180000,
        source_labels=["fixture"],
        metric_snapshot=CreatorMetricSnapshotPayload(
            captured_at=datetime.now(UTC),
            follower_count=180000,
            average_views_30d=18000,
            engagement_rate_30d=Decimal("0.0410"),
            source="fixture",
        ),
    )


async def test_execute_creator_ingest_uses_session_factory(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    """The activity helper should ingest creator data through the configured session factory."""

    monkeypatch.setattr(
        "ima.temporal.activities.get_session_factory",
        lambda: sqlite_session_factory,
    )

    result = await execute_creator_ingest(_ingest_payload())

    assert result.created is True
    assert result.snapshot_recorded is True
    assert result.score.creator_id == result.creator_id


async def test_creator_ingest_workflow_executes_activity(monkeypatch) -> None:
    """The workflow should dispatch the named activity with the expected queue and retry policy."""

    payload = _ingest_payload()
    expected = CreatorIngestResult(
        creator_id="creator-1",
        created=True,
        content_created=0,
        content_updated=0,
        snapshot_recorded=True,
        score={
            "creator_id": "creator-1",
            "growth_score": 80,
            "commercial_readiness_score": 70,
            "fraud_risk_score": 20,
            "evidence_coverage_score": 80,
            "is_qualified": True,
            "qualification_reasons": [],
        },
    )
    captured: dict[str, object] = {}

    async def fake_execute_activity(
        activity_name: str,
        activity_payload: CreatorIngestInput,
        **kwargs: object,
    ) -> CreatorIngestResult:
        captured["activity_name"] = activity_name
        captured["payload"] = activity_payload
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr("ima.temporal.workflows.workflow.execute_activity", fake_execute_activity)

    result = await CreatorIngestWorkflow().run(payload)

    assert result == expected
    assert captured["activity_name"] == CREATOR_INGEST_ACTIVITY
    assert captured["payload"] == payload
    kwargs = captured["kwargs"]
    assert kwargs["task_queue"] == CREATOR_TASK_QUEUE
    assert kwargs["result_type"] is CreatorIngestResult
    assert kwargs["retry_policy"] == RetryPolicy(maximum_attempts=3)
