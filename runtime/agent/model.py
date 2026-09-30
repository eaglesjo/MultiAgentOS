"""Model-backed AgentExecutor for provider-neutral AGENT_EXECUTION_RUNTIME agents."""

from __future__ import annotations

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor
from core.contracts.model_runtime import ModelAdapter, ModelRequest, ModelResponse
from core.contracts.agent_execution_runtime import RuntimeEvent
from runtime.quota import QuotaIntelligence
from runtime.capability import CapabilityRegistry
from runtime.health import ModelHealthRegistry
from runtime.model_control import ModelControlPlane
from runtime.tool_calling import ToolCallingExecution, ToolCallingRuntime, ToolRuntime
from core.contracts.work_unit import WorkUnit
from core.contracts.execution_limits import ExecutionBudget, RateLimit
from core.execution_limits import ExecutionLimitStore


class ModelAgentExecutor(AgentExecutor):
    """Turn a WorkUnit into a model request and return the model response."""

    def __init__(
        self,
        adapters: dict[str, ModelAdapter],
        models: list[ModelSpec],
        system_prompt: str | None = None,
        fallback_model_ids: tuple[str, ...] = (),
        quota_intelligence: QuotaIntelligence | None = None,
        health_registry: ModelHealthRegistry | None = None,
        model_control: ModelControlPlane | None = None,
        capability_registry: CapabilityRegistry | None = None,
        event_sink: object | None = None,
        ledger_store: object | None = None,
        cursor_store: object | None = None,
        limit_store: ExecutionLimitStore | None = None,
        execution_budget: ExecutionBudget | None = None,
        rate_limit: RateLimit | None = None,
    ):
        self.adapters = dict(adapters)
        self.models = {model.id: model for model in models}
        self.system_prompt = system_prompt
        self.fallback_model_ids = tuple(fallback_model_ids)
        self.quota_intelligence = quota_intelligence
        self.health_registry = health_registry
        self.model_control = model_control
        self.capability_registry = capability_registry
        self.event_sink = event_sink
        self.ledger_store = ledger_store
        self.cursor_store = cursor_store
        self.limit_store = limit_store
        self.execution_budget = execution_budget
        self.rate_limit = rate_limit

    def _candidate_model_ids(self, model_id: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys((model_id, *self.fallback_model_ids)))

    @staticmethod
    def _is_failover_error(exc: Exception) -> bool:
        """Return True for errors where another model/provider may succeed."""
        status = getattr(exc, "status_code", getattr(exc, "status", None))
        code = str(getattr(exc, "code", "")).lower()
        message = str(exc).lower()
        if status in {408, 429, 500, 502, 503, 504}:
            return True
        transient_codes = (
            "rate_limit", "rate-limit", "quota", "resource_exhausted",
            "too_many_requests", "temporarily_unavailable",
            "service_unavailable", "unavailable", "overloaded", "timeout",
        )
        return any(token in code or token in message for token in transient_codes)

    def execute(
        self, *, agent: AgentContract, model_id: str, work_unit: WorkUnit
    ) -> ModelResponse:
        attempts: list[str] = []
        last_error: Exception | None = None
        for candidate_id in self._candidate_model_ids(model_id):
            if agent.model_ids and candidate_id not in agent.model_ids:
                continue
            try:
                model = self.models[candidate_id]
                adapter_id = str(model.metadata.get("adapter_id", model.provider_id))
                adapter = self.adapters[adapter_id]
                system = self.system_prompt or str(agent.metadata.get("system_prompt", "")) or None
                request = ModelRequest(
                    prompt=work_unit.objective,
                    system=system,
                    metadata={"agent_id": agent.id, "work_unit_id": work_unit.id, "attempts": tuple(attempts)},
                )
                response = adapter.generate(model, request)
                attempts.append(candidate_id)
                metadata = dict(response.metadata)
                metadata["attempts"] = tuple(attempts)
                response = ModelResponse(
                    text=response.text,
                    model_id=response.model_id or candidate_id,
                    metadata=metadata,
                )
                work_unit.metadata["model_response"] = response.text
                work_unit.metadata["model_id"] = response.model_id
                work_unit.metadata["model_adapter"] = adapter_id
                work_unit.metadata["model_attempts"] = tuple(attempts)
                if self.capability_registry is not None:
                    self.capability_registry.observe_response(model, metadata)
                if self.quota_intelligence is not None:
                    snapshot = self.quota_intelligence.observe_response(model, metadata)
                    work_unit.metadata["quota_snapshot"] = {
                        "confidence": snapshot.confidence.value,
                        "dimensions": {
                            item.name: {"remaining": item.remaining, "limit": item.limit}
                            for item in snapshot.dimensions
                        },
                    }
                if self.model_control is not None:
                    self.model_control.record_success(model, metadata)
                elif self.health_registry is not None:
                    self.health_registry.record_success(candidate_id, model.provider_id)
                return response
            except Exception as exc:
                attempts.append(candidate_id)
                last_error = exc
                if self.model_control is not None and candidate_id in self.models:
                    self.model_control.record_failure(self.models[candidate_id], exc)
                elif self.health_registry is not None and candidate_id in self.models:
                    self.health_registry.record_failure(candidate_id, self.models[candidate_id].provider_id, exc)
                if not self._is_failover_error(exc):
                    raise
        if last_error is not None:
            raise last_error
        raise LookupError(f"No executable model available for agent {agent.id}")

    def execute_with_tools(
        self,
        *,
        agent: AgentContract,
        model_id: str,
        work_unit: WorkUnit,
        tool_runtime: ToolRuntime,
        approved: bool = False,
    ) -> ToolCallingExecution:
        """Execute the selected model through Tool Calling with ordered fallback."""
        attempts: list[str] = []
        last_error: Exception | None = None
        for candidate_id in self._candidate_model_ids(model_id):
            if agent.model_ids and candidate_id not in agent.model_ids:
                continue
            try:
                model = self.models.get(candidate_id)
                if model is None:
                    raise LookupError(f"Model not registered: {candidate_id}")
                adapter_id = str(model.metadata.get("adapter_id", model.provider_id))
                adapter = self.adapters.get(adapter_id)
                if adapter is None:
                    raise LookupError(f"Model adapter not registered: {adapter_id}")
                request = ModelRequest(
                    prompt=work_unit.objective,
                    system=self.system_prompt or str(agent.metadata.get("system_prompt", "")) or None,
                    metadata={
                        "agent_id": agent.id,
                        "work_unit_id": work_unit.id,
                        "attempts": tuple(attempts),
                    },
                )
                runtime = ToolCallingRuntime(
                    models={candidate_id: model},
                    adapters={candidate_id: adapter},
                    tools=tool_runtime,
                    event_sink=self.event_sink,
                    ledger_store=self.ledger_store,
                    cursor_store=self.cursor_store,
                    agent_id=agent.id,
                    limit_store=self.limit_store,
                    execution_budget=self.execution_budget,
                    rate_limit=self.rate_limit,
                )
                if work_unit.metadata.get("resume_from_cursor"):
                    result = runtime.resume(
                        request,
                        model_id=candidate_id,
                        work_unit_id=work_unit.id,
                        granted_permissions=agent.permissions,
                        approved=approved,
                    )
                else:
                    result = runtime.execute(
                        request,
                        model_id=candidate_id,
                        work_unit_id=work_unit.id,
                        granted_permissions=agent.permissions,
                        approved=approved,
                    )
                attempts.append(candidate_id)
                work_unit.metadata["model_response"] = result.response.text
                work_unit.metadata["model_id"] = result.model_id
                work_unit.metadata["model_adapter"] = adapter_id
                work_unit.metadata["tool_rounds"] = result.rounds
                work_unit.metadata["tool_results"] = tuple(result.tool_results)
                work_unit.metadata["model_attempts"] = tuple(attempts)
                if self.capability_registry is not None:
                    self.capability_registry.observe_response(model, dict(result.response.metadata))
                if self.quota_intelligence is not None:
                    snapshot = self.quota_intelligence.observe_response(model, dict(result.response.metadata))
                    work_unit.metadata["quota_snapshot"] = {
                        "confidence": snapshot.confidence.value,
                        "dimensions": {
                            item.name: {"remaining": item.remaining, "limit": item.limit}
                            for item in snapshot.dimensions
                        },
                    }
                if self.model_control is not None:
                    self.model_control.record_success(model, dict(result.response.metadata))
                elif self.health_registry is not None:
                    self.health_registry.record_success(candidate_id, model.provider_id)
                return result
            except Exception as exc:
                attempts.append(candidate_id)
                last_error = exc
                if self.model_control is not None and candidate_id in self.models:
                    self.model_control.record_failure(self.models[candidate_id], exc)
                elif self.health_registry is not None and candidate_id in self.models:
                    self.health_registry.record_failure(candidate_id, self.models[candidate_id].provider_id, exc)
                if not self._is_failover_error(exc):
                    raise
        if last_error is not None:
            raise last_error
        raise LookupError(f"No executable tool-calling model available for agent {agent.id}")

