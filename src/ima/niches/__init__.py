"""YAML-backed niche configuration loading for discovery and scoring."""

from ima.niches.config import NicheConfig
from ima.niches.registry import NicheRegistry, get_niche_registry

__all__ = ["NicheConfig", "NicheRegistry", "get_niche_registry"]
