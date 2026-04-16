"""Agent contract base model and prompt rendering helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import BaseModel, ConfigDict, Field

from ima.providers.llm.base import LLMMessage


class AgentContract(BaseModel):
    """Versioned agent contract used by the executor runtime."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    version: str = Field(description="Semantic version of the contract.")
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    system_prompt_template_path: Path
    model_preference: list[str]
    temperature: float = 0.7
    max_tokens: int = 4096
    few_shot_examples: list[dict[str, Any]] | None = None
    tools: list[BaseModel] | None = None

    def render_prompt(self, inputs: BaseModel) -> list[LLMMessage]:
        """Render the system prompt and normalized messages for a run."""

        loader = FileSystemLoader(str(self.system_prompt_template_path.parent))
        environment = Environment(loader=loader, undefined=StrictUndefined, autoescape=False)
        template = environment.get_template(self.system_prompt_template_path.name)
        system_prompt = template.render(
            contract_name=self.name,
            contract_version=self.version,
            description=self.description,
            inputs=inputs.model_dump(mode="json"),
        )

        messages: list[LLMMessage] = [LLMMessage(role="system", content=system_prompt)]
        for example in self.few_shot_examples or []:
            if "input" in example:
                messages.append(
                    LLMMessage(
                        role="user",
                        content=json.dumps(example["input"], indent=2, ensure_ascii=False),
                    )
                )
            if "output" in example:
                messages.append(
                    LLMMessage(
                        role="assistant",
                        content=json.dumps(example["output"], indent=2, ensure_ascii=False),
                    )
                )

        messages.append(
            LLMMessage(
                role="user",
                content=json.dumps(inputs.model_dump(mode="json"), indent=2, ensure_ascii=False),
            )
        )
        return messages
