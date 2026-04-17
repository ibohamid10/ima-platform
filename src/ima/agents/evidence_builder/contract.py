"""Evidence builder agent contract and typed I/O schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ima.agents.contract import AgentContract


class EvidenceContentRecord(BaseModel):
    """Structured recent-content record supplied to the evidence builder agent."""

    title: str | None = None
    caption: str | None = None
    source_uri: str
    source_type: str
    hashtags: list[str] = Field(default_factory=list)
    detected_brands: list[str] = Field(default_factory=list)
    sponsor_probability: float | None = Field(default=None, ge=0.0, le=1.0)


class EvidenceBuilderInput(BaseModel):
    """Input payload for the evidence builder agent."""

    creator_handle: str
    platform: Literal["youtube", "instagram", "tiktok"]
    bio: str | None = None
    recent_content: list[EvidenceContentRecord] = Field(default_factory=list)
    metrics: dict[str, object] = Field(default_factory=dict)
    existing_brands: list[str] = Field(default_factory=list)


class GeneratedEvidenceItem(BaseModel):
    """One evidence item produced by the evidence builder agent."""

    claim_text: str
    source_uri: str
    source_type: str
    confidence: float = Field(ge=0.0, le=1.0)


class EvidenceBuilderOutput(BaseModel):
    """Output payload for the evidence builder agent."""

    evidence_items: list[GeneratedEvidenceItem]

    @field_validator("evidence_items")
    @classmethod
    def validate_evidence_items(
        cls,
        value: list[GeneratedEvidenceItem],
    ) -> list[GeneratedEvidenceItem]:
        """Ensure every item contains the minimum required fields."""

        if not value:
            raise ValueError("evidence_items darf nicht leer sein.")
        return value


EVIDENCE_BUILDER_CONTRACT = AgentContract(
    name="evidence_builder",
    version="1.0.0",
    description="Erzeugt strukturierte Evidence-Items mit source_uri und confidence.",
    input_schema=EvidenceBuilderInput,
    output_schema=EvidenceBuilderOutput,
    system_prompt_template_path=Path("src/ima/agents/evidence_builder/prompts/system.j2"),
    model_preference=["claude-sonnet-4-6", "gpt-5.4"],
    temperature=0.2,
    max_tokens=2048,
)
