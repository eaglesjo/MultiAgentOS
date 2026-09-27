"""Model-backed AgentExecutor for provider-neutral VYRELON agents."""

from __future__ import annotations

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor
from core.contracts.model_runtime import ModelAdapter, ModelRequest, ModelResponse
from runtime.tool_calling import ToolCallingExecution, ToolCallingRuntime, ToolRuntime
from core.contracts.work_unit import WorkUnit


class ModelAgentExecutor(AgentExecutor):
    """Turn a WorkUnit into a model request and return the model response."""

    def __init__(
        self,
        adapters: dict[str, ModelAdapter],
        models: list[ModelSpec],
        system_prompt: str | None = None,
    ):
        self.adapters = dict(adapters)
        self.models = {model.id: model for model in models}
        self.system_prompt = system_prompt

    def execute(
        self, *, agent: AgentContract, model_id: str, work_unit: WorkUnit
    ) -> ModelResponse:
        if agent.model_ids and model_id not in agent.model_ids:
            raise PermissionError(
                f"Model {model_id} is not assigned to agent {agent.id}"
            )
        try:
            model = self.models[model_id]
        except KeyError as exc:
            raise LookupError(f"Model not registered: {model_id}") from exc

        adapter_id = str(model.metadata.get("adapter_id", model.provider_id))
        try:
            adapter = self.adapters[adapter_id]
        except KeyError as exc:
            raise LookupError(f"Model adapter not registered: {adapter_id}") from exc

        system = self.system_prompt or str(agent.metadata.get("system_prompt", "")) or None
        request = ModelRequest(
            prompt=work_unit.objective,
            system=system,
            metadata={"agent_id": agent.id, "work_unit_id": work_unit.id},
        )
        response = adapter.generate(model, request)
        work_unit.metadata["model_response"] = response.text
        work_unit.metadata["model_id"] = response.model_id
        work_unit.metadata["model_adapter"] = adapter_id
        return response

    def execute_with_tools(
        self,
        *,
        agent: AgentContract,
        model_id: str,
        work_unit: WorkUnit,
        tool_runtime: ToolRuntime,
        approved: bool = False,
    ) -> ToolCallingExecution:
        """Execute the selected model through the normalized Tool Calling runtime."""
        if agent.model_ids and model_id not in agent.model_ids:
            raise PermissionError(f"Model {model_id} is not assigned to agent {agent.id}")
        model = self.models.get(model_id)
        if model is None:
            raise LookupError(f"Model not registered: {model_id}")
        adapter_id = str(model.metadata.get("adapter_id", model.provider_id))
        adapter = self.adapters.get(adapter_id)
        if adapter is None:
            raise LookupError(f"Model adapter not registered: {adapter_id}")
        request = ModelRequest(
            prompt=work_unit.objective,
            system=self.system_prompt or str(agent.metadata.get("system_prompt", "")) or None,
            metadata={"agent_id": agent.id, "work_unit_id": work_unit.id},
        )
        runtime = ToolCallingRuntime(
            models={model_id: model},
            adapters={model_id: adapter},
            tools=tool_runtime,
        )
        result = runtime.execute(
            request,
            model_id=model_id,
            work_unit_id=work_unit.id,
            granted_permissions=agent.permissions,
            approved=approved,
        )
        work_unit.metadata["model_response"] = result.response.text
        work_unit.metadata["model_id"] = result.model_id
        work_unit.metadata["model_adapter"] = adapter_id
        work_unit.metadata["tool_rounds"] = result.rounds
        work_unit.metadata["tool_results"] = tuple(result.tool_results)
        return result
