"""Registry that loads all YAML-defined niches from disk."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from ima.config import settings
from ima.niches.config import NicheConfig


class NicheRegistry:
    """In-memory registry for configured niches."""

    def __init__(self, config_dir: str | Path | None = None) -> None:
        """Load all niche YAML files from the configured directory."""

        self.config_dir = Path(config_dir or settings.niches_config_dir)
        self._niches = self._load_configs()

    def _load_configs(self) -> dict[str, NicheConfig]:
        """Load and validate every niche YAML file from disk."""

        niches: dict[str, NicheConfig] = {}
        if not self.config_dir.exists():
            return niches

        for path in sorted(self.config_dir.glob("*.yaml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            niche = NicheConfig.model_validate(payload)
            niches[niche.niche_id] = niche
        return niches

    def all(self) -> list[NicheConfig]:
        """Return all configured niches in deterministic order."""

        return list(self._niches.values())

    def get(self, niche_id: str) -> NicheConfig:
        """Return one niche configuration or raise a clear error."""

        normalized = niche_id.strip().lower()
        niche = self._niches.get(normalized)
        if niche is None:
            available = ", ".join(sorted(self._niches)) or "keine"
            raise ValueError(
                f"Unbekannte Nische '{niche_id}'. Verfuegbare Nischen: {available}."
            )
        return niche

    def has(self, niche_id: str) -> bool:
        """Return whether the given niche exists."""

        return niche_id.strip().lower() in self._niches


@lru_cache(maxsize=1)
def get_niche_registry() -> NicheRegistry:
    """Return a cached registry for the configured niche directory."""

    return NicheRegistry()
