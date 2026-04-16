"""Agent executor responsible for provider selection, retries, and logging."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, time, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ima.agents.contract import AgentContract
from ima.agents.exceptions import AgentInputValidationError, AgentProviderSelectionError
from ima.config import settings
from ima.db.models import AgentRun, ValidationStatus
from ima.providers.llm.base import LLMMessage, LLMProvider
from ima.providers.llm.exceptions import (
    LLMBudgetExceededError,
    LLMProviderUnavailableError,
    LLMSchemaValidationError,
)


class AgentExecutor:
    """Run an agent contract against configured provider adapters."""

    def __init__(
        self,
        contract: AgentContract,
        llm_providers: dict[str, LLMProvider],
        db_session_factory: async_sessionmaker,
        langfuse_hook: Any,
    ) -> None:
        """Create a new executor for a single agent contract."""

        self.contract = contract
        self.llm_providers = llm_providers
        self.db_session_factory = db_session_factory
        self.langfuse_hook = langfuse_hook
        self.last_run_info: dict[str, Any] | None = None

    async def run(self, inputs: BaseModel) -> BaseModel:
        """Execute the contract with one schema retry and provider fallback."""

        validated_inputs = self._validate_inputs(inputs)
        await self._ensure_budget_available()

        messages = self.contract.render_prompt(validated_inputs)
        input_payload = validated_inputs.model_dump(mode="json")
        input_hash = self._hash_payload(input_payload)
        candidates = self._candidate_pairs()
        if not candidates:
            raise AgentProviderSelectionError(
                f"Kein Provider unterstuetzt Modelle {self.contract.model_preference}."
            )

        initial_provider_name, initial_provider, initial_model = candidates[0]
        trace = self.langfuse_hook.start_trace(
            name=f"agent:{self.contract.name}",
            input_payload=input_payload,
            metadata={"contract_version": self.contract.version},
        )

        async with self.db_session_factory() as session:
            run_record = AgentRun(
                agent_name=self.contract.name,
                contract_version=self.contract.version,
                provider=initial_provider_name,
                model=initial_model,
                input_hash=input_hash,
                input_json=input_payload,
                output_json=None,
                validation_status=ValidationStatus.PENDING.value,
                validation_attempts=1,
                started_at=datetime.now(timezone.utc),
                trace_id=trace.trace_id,
            )
            session.add(run_record)
            await session.flush()

            provider_error_messages: list[str] = []

            for provider_name, provider, model in candidates:
                generation = self.langfuse_hook.start_generation(
                    name=self.contract.name,
                    model=model,
                    provider=provider_name,
                    input_payload=[message.model_dump() for message in messages],
                )
                try:
                    output_model, response, attempts = await self._attempt_completion(
                        provider=provider,
                        provider_name=provider_name,
                        model=model,
                        messages=messages,
                    )
                    now = datetime.now(timezone.utc)
                    run_record.provider = provider_name
                    run_record.model = model
                    run_record.output_json = output_model.model_dump(mode="json")
                    run_record.validation_status = ValidationStatus.SUCCESS.value
                    run_record.validation_attempts = attempts
                    run_record.input_tokens = response.input_tokens
                    run_record.output_tokens = response.output_tokens
                    run_record.cost_usd = response.cost_usd
                    run_record.latency_ms = int((now - run_record.started_at).total_seconds() * 1000)
                    run_record.completed_at = now
                    run_record.error_message = None
                    await session.commit()

                    generation.update(
                        output=run_record.output_json,
                        usage_details={
                            "input_tokens": response.input_tokens,
                            "output_tokens": response.output_tokens,
                        },
                    )
                    generation.finish()
                    trace.finish(output=run_record.output_json)
                    self.langfuse_hook.flush()
                    self.last_run_info = {
                        "trace_id": trace.trace_id,
                        "trace_url": trace.trace_url,
                        "cost_usd": str(response.cost_usd),
                        "latency_ms": run_record.latency_ms,
                        "run_id": str(run_record.id),
                    }
                    return output_model
                except LLMProviderUnavailableError as exc:
                    provider_error_messages.append(f"{provider_name}:{model}:{exc}")
                    generation.update(level="WARNING", output={"error": str(exc)})
                    generation.finish()
                    continue
                except LLMSchemaValidationError as exc:
                    now = datetime.now(timezone.utc)
                    run_record.provider = provider_name
                    run_record.model = model
                    run_record.validation_status = ValidationStatus.SCHEMA_FAILED.value
                    run_record.validation_attempts = 2
                    run_record.latency_ms = int((now - run_record.started_at).total_seconds() * 1000)
                    run_record.completed_at = now
                    run_record.error_message = str(exc)
                    await session.commit()
                    generation.update(level="ERROR", output={"error": str(exc)})
                    generation.finish()
                    trace.finish(output={"error": str(exc)})
                    self.langfuse_hook.flush()
                    raise

            now = datetime.now(timezone.utc)
            error_message = "; ".join(provider_error_messages) or "Kein Provider war verfuegbar."
            run_record.validation_status = ValidationStatus.PROVIDER_ERROR.value
            run_record.latency_ms = int((now - run_record.started_at).total_seconds() * 1000)
            run_record.completed_at = now
            run_record.error_message = error_message
            await session.commit()
            trace.finish(output={"error": error_message})
            self.langfuse_hook.flush()
            raise LLMProviderUnavailableError(error_message)

    async def _attempt_completion(
        self,
        provider: LLMProvider,
        provider_name: str,
        model: str,
        messages: list[LLMMessage],
    ) -> tuple[BaseModel, Any, int]:
        """Run one completion attempt with at most one schema retry."""

        response = await provider.complete(
            messages=messages,
            model=model,
            response_schema=self.contract.output_schema,
            temperature=self.contract.temperature,
            max_tokens=self.contract.max_tokens,
        )
        try:
            return self._validate_output(response.content), response, 1
        except LLMSchemaValidationError:
            retry_messages = [
                *messages,
                LLMMessage(role="assistant", content=response.content),
                LLMMessage(
                    role="user",
                    content=(
                        "Die letzte Antwort entsprach nicht dem geforderten Schema. "
                        "Antworte erneut ausschliesslich mit einer gueltigen JSON-Struktur."
                    ),
                ),
            ]
            retry_response = await provider.complete(
                messages=retry_messages,
                model=model,
                response_schema=self.contract.output_schema,
                temperature=self.contract.temperature,
                max_tokens=self.contract.max_tokens,
            )
            try:
                return self._validate_output(retry_response.content), retry_response, 2
            except LLMSchemaValidationError as exc:
                raise LLMSchemaValidationError(
                    f"Schema-Validierung fuer {provider_name}/{model} zweimal fehlgeschlagen."
                ) from exc

    def _validate_inputs(self, inputs: BaseModel) -> BaseModel:
        """Validate raw inputs against the declared input schema."""

        try:
            return self.contract.input_schema.model_validate(inputs.model_dump(mode="json"))
        except ValidationError as exc:
            raise AgentInputValidationError(str(exc)) from exc

    def _validate_output(self, content: str) -> BaseModel:
        """Parse and validate a structured output payload."""

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMSchemaValidationError("Provider-Antwort war kein gueltiges JSON.") from exc
        try:
            return self.contract.output_schema.model_validate(parsed)
        except ValidationError as exc:
            raise LLMSchemaValidationError(str(exc)) from exc

    def _candidate_pairs(self) -> list[tuple[str, LLMProvider, str]]:
        """Return provider/model pairs in fallback order."""

        pairs: list[tuple[str, LLMProvider, str]] = []
        # DECISION: DECISIONS.md#2026-04-16--keine-agent-sdks
        for model in self.contract.model_preference:
            for provider_name, provider in self.llm_providers.items():
                if provider.supports_model(model):
                    pairs.append((provider_name, provider, model))
        return pairs

    def _hash_payload(self, payload: dict[str, Any]) -> str:
        """Create a deterministic SHA-256 hash for input payloads."""

        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def _ensure_budget_available(self) -> None:
        """Block execution when the configured daily budget is exhausted."""

        day_start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        async with self.db_session_factory() as session:
            query = select(func.coalesce(func.sum(AgentRun.cost_usd), Decimal("0"))).where(
                AgentRun.started_at >= day_start
            )
            spent = await session.scalar(query)
        spent_decimal = spent if isinstance(spent, Decimal) else Decimal(str(spent or 0))
        if spent_decimal >= Decimal(str(settings.llm_daily_budget_usd)):
            raise LLMBudgetExceededError("Das taegliche LLM-Budget ist bereits ausgeschoepft.")
