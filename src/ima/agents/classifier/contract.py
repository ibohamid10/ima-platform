"""Classifier agent contract and concrete input/output schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ima.agents.contract import AgentContract


class ClassifierInput(BaseModel):
    """Input payload for the classifier agent."""

    creator_handle: str
    platform: Literal["youtube", "instagram", "tiktok"]
    bio: str
    recent_captions: list[str]
    top_hashtags: list[str]

    @field_validator("recent_captions")
    @classmethod
    def validate_recent_captions(cls, value: list[str]) -> list[str]:
        """Keep the prompt surface small and predictable."""

        if len(value) > 5:
            raise ValueError("recent_captions darf maximal 5 Eintraege enthalten.")
        return value

    @field_validator("top_hashtags")
    @classmethod
    def validate_top_hashtags(cls, value: list[str]) -> list[str]:
        """Keep hashtag input bounded."""

        if len(value) > 10:
            raise ValueError("top_hashtags darf maximal 10 Eintraege enthalten.")
        return value


class ClassifierOutput(BaseModel):
    """Output payload produced by the classifier agent."""

    niche: str
    sub_niches: list[str]
    language: str
    brand_safety_score: int = Field(ge=0, le=10)
    reasoning: str


CLASSIFIER_CONTRACT = AgentContract(
    name="classifier",
    version="1.0.0",
    description="Klassifiziert Creator nach Nische, Sprache und Brand-Safety.",
    input_schema=ClassifierInput,
    output_schema=ClassifierOutput,
    system_prompt_template_path=Path("src/ima/agents/classifier/prompts/system.j2"),
    model_preference=["claude-haiku-4-5-20251001", "gpt-5.4-nano"],
    temperature=0.3,
    max_tokens=1024,
)
