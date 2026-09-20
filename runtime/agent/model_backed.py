"""Agent executor backed by the provider-neutral model runtime."""

from __future__ import annotations

import json

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.work_unit import WorkUnit
from core.registry import AIRegistry
from runtime.model.invoker import ModelInvoker


class ModelBackedAgentExecutor:
    """Turn an assigned model into an executable VYRELON Agent."""

    def __init__(self, ai_registry: AIRegistry, model_invoker: ModelInvoker) -> None:
        self.ai_registry = ai_registry
        self.model_invoker = model_invoker

    def execute(
        self, *, agent: AgentContract, model_id: str, work_unit: WorkUnit
    ) -> ModelResponse:
        model = self.ai_registry.model(model_id)
        request = ModelRequest(
            system=self._system_prompt(agent),
            prompt=self._work_prompt(work_unit),
            metadata={
                "agent_id": agent.id,
                "role": agent.role,
                "work_unit_id": work_unit.id,
            },
        )
        return self.model_invoker.generate(model, request)

    @staticmethod
    def _system_prompt(agent: AgentContract) -> str:
        capabilities = ", ".join(sorted(agent.capabilities)) or "general development"
        return (
            f"You are the VYRELON {agent.role} agent. "
            f"Your capabilities are: {capabilities}. "
            "Work only within the objective and permissions provided by the orchestrator."
        )

    @staticmethod
    def _work_prompt(work_unit: WorkUnit) -> str:
        inputs = json.dumps(work_unit.inputs, ensure_ascii=False, sort_keys=True, default=str)
        return f"Objective: {work_unit.objective}\nInputs: {inputs}"
