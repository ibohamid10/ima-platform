"""Thin Langfuse wrapper with a no-op fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langfuse import Langfuse

from ima.config import settings
from ima.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GenerationHandle:
    """Handle for a Langfuse generation span."""

    trace_id: str | None
    observation: Any | None = None
    context_manager: Any | None = None

    def update(self, **kwargs: Any) -> None:
        """Update the active generation span if available."""

        if self.observation is not None:
            self.observation.update(**kwargs)

    def finish(self) -> None:
        """Close the active generation span if one exists."""

        if self.context_manager is not None:
            self.context_manager.__exit__(None, None, None)


@dataclass
class TraceHandle:
    """Handle for a Langfuse trace/span."""

    trace_id: str | None
    base_url: str
    observation: Any | None = None
    context_manager: Any | None = None

    @property
    def trace_url(self) -> str | None:
        """Return a best-effort trace URL for local debugging."""

        if not self.trace_id:
            return None
        project_id = settings.langfuse_project_id or "default"
        return f"{self.base_url.rstrip('/')}/project/{project_id}/traces/{self.trace_id}"

    def finish(self, **kwargs: Any) -> None:
        """Close the active trace span if one exists."""

        if self.observation is not None and kwargs:
            self.observation.update(**kwargs)
        if self.context_manager is not None:
            self.context_manager.__exit__(None, None, None)


class LangfuseHook:
    """Wrapper around the Langfuse SDK that degrades to a no-op."""

    def __init__(self) -> None:
        """Create a new Langfuse hook using environment configuration."""

        self.base_url = settings.effective_langfuse_base_url
        self._client: Any | None = None
        self.enabled = settings.langfuse_enabled

        if not self.enabled:
            logger.warning("langfuse_disabled")
            return

        self._client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=self.base_url,
            timeout=5,
        )

    def start_trace(
        self,
        name: str,
        input_payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> TraceHandle:
        """Start a trace/span for an agent run."""

        if not self.enabled or self._client is None:
            return TraceHandle(trace_id=None, base_url=self.base_url)

        context_manager = self._client.start_as_current_observation(
            as_type="span",
            name=name,
            input=input_payload,
            metadata=metadata,
        )
        observation = context_manager.__enter__()
        trace_id = getattr(observation, "trace_id", None) or getattr(observation, "id", None)
        return TraceHandle(
            trace_id=trace_id,
            base_url=self.base_url,
            observation=observation,
            context_manager=context_manager,
        )

    def start_generation(
        self,
        name: str,
        model: str,
        provider: str,
        input_payload: list[dict[str, str]],
    ) -> GenerationHandle:
        """Start a generation span for an LLM call."""

        if not self.enabled or self._client is None:
            return GenerationHandle(trace_id=None)

        context_manager = self._client.start_as_current_observation(
            as_type="generation",
            name=name,
            model=model,
            input=input_payload,
            metadata={"provider": provider},
        )
        observation = context_manager.__enter__()
        trace_id = getattr(observation, "trace_id", None)
        return GenerationHandle(
            trace_id=trace_id,
            observation=observation,
            context_manager=context_manager,
        )

    def flush(self) -> None:
        """Flush queued telemetry events if the SDK is active."""

        if self.enabled and self._client is not None:
            self._client.flush()
