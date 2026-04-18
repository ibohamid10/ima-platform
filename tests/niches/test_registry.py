"""Tests for YAML-backed niche configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from ima.niches import NicheRegistry


def test_niche_registry_loads_all_yaml_configs(tmp_path: Path) -> None:
    """Registry should validate and expose all niche YAML files."""

    config_dir = tmp_path / "niches"
    config_dir.mkdir()
    (config_dir / "productivity.yaml").write_text(
        """
niche_id: productivity
display_name: Productivity
discovery:
  youtube_keywords: ["notion workflow"]
  hashtag_seeds: ["#productivity"]
  min_subscribers: 50000
  max_subscribers: 500000
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
    (config_dir / "tech.yaml").write_text(
        """
niche_id: tech
display_name: Tech
discovery:
  youtube_keywords: ["ai tools"]
  hashtag_seeds: ["#tech"]
  min_subscribers: 50000
  max_subscribers: 500000
  languages: ["en"]
  regions: ["US"]
scoring:
  niche_fit:
    primary_labels: ["tech"]
    secondary_labels: ["ai"]
    primary_weight: 0.6
    secondary_weight: 0.4
brand_signals:
  categories: ["AI Software"]
  keywords_creator_programs: ["partner program"]
  keywords_hiring: ["influencer marketing"]
""".strip(),
        encoding="utf-8",
    )

    registry = NicheRegistry(config_dir)

    assert sorted(niche.niche_id for niche in registry.all()) == ["productivity", "tech"]
    assert registry.get("productivity").discovery.youtube_keywords == ["notion workflow"]


def test_niche_registry_raises_clear_error_for_unknown_niche(tmp_path: Path) -> None:
    """Unknown niche lookups should mention the available options."""

    config_dir = tmp_path / "niches"
    config_dir.mkdir()
    (config_dir / "productivity.yaml").write_text(
        """
niche_id: productivity
display_name: Productivity
discovery:
  youtube_keywords: ["notion workflow"]
  hashtag_seeds: ["#productivity"]
  min_subscribers: 50000
  max_subscribers: 500000
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

    registry = NicheRegistry(config_dir)

    with pytest.raises(ValueError, match="Verfuegbare Nischen: productivity"):
        registry.get("unknown")
