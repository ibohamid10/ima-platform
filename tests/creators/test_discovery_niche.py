"""Tests for niche-backed YouTube discovery request construction."""

from __future__ import annotations

from pathlib import Path

import pytest

from ima.cli.run_agent import _discover_youtube
from ima.niches import NicheRegistry


@pytest.mark.asyncio()
async def test_discover_youtube_uses_niche_config(monkeypatch, tmp_path: Path) -> None:
    """Niche discovery should derive keywords and subscriber filters from YAML config."""

    config_dir = tmp_path / "niches"
    config_dir.mkdir()
    (config_dir / "productivity.yaml").write_text(
        """
niche_id: productivity
display_name: Productivity
discovery:
  youtube_keywords: ["notion workflow", "desk setup"]
  hashtag_seeds: ["#productivity"]
  min_subscribers: 50000
  max_subscribers: 1000000
  languages: ["en"]
  regions: ["US"]
scoring:
  niche_fit:
    primary_labels: ["productivity"]
    secondary_labels: ["notion"]
    primary_weight: 0.6
    secondary_weight: 0.4
brand_signals:
  categories: ["SaaS"]
  keywords_creator_programs: ["affiliate"]
  keywords_hiring: ["creator partnerships"]
""".strip(),
        encoding="utf-8",
    )
    seen_requests = []

    class StubHarvester:
        async def discover_channels(self, request):
            seen_requests.append(request)
            return []

    class StubImportService:
        async def import_records(self, *args, **kwargs):
            return type(
                "ImportResult",
                (),
                {
                    "results": [],
                    "model_dump": lambda self, mode="json": {
                        "total_records": 0,
                        "imported_count": 0,
                    },
                },
            )()

    monkeypatch.setattr(
        "ima.cli.run_agent.get_niche_registry",
        lambda: NicheRegistry(config_dir),
    )
    monkeypatch.setattr("ima.cli.run_agent.YouTubeDataAPIHarvester", lambda: StubHarvester())
    monkeypatch.setattr(
        "ima.cli.run_agent.CreatorSourceImportService",
        lambda: StubImportService(),
    )
    monkeypatch.setattr("ima.cli.run_agent.typer.echo", lambda *args, **kwargs: None)

    await _discover_youtube(
        keywords=None,
        niche="productivity",
        language=None,
        region=None,
        min_subscribers=None,
        max_subscribers=None,
        max_results_per_keyword=5,
        max_videos=5,
        via_temporal=False,
        workflow_prefix="test",
        task_queue="test",
    )

    assert len(seen_requests) == 1
    request = seen_requests[0]
    assert request.keywords == ["notion workflow", "desk setup"]
    assert request.min_subscribers == 50000
    assert request.max_subscribers == 1000000
    assert request.source_labels == ["youtube_keyword_discovery", "niche:productivity"]
