"""Deterministic AI assignment and fallback routing."""

from dataclasses import dataclass

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec


@dataclass(frozen=True)
class Assignment:
    agent_id: str
    model_id: str


class AIRouter:
    def assign(
        self,
        agent: AgentContract,
        models: list[ModelSpec],
        preferred_model_ids: list[str] | None = None,
    ) -> Assignment:
        preferred = preferred_model_ids or list(agent.model_ids)
        by_id = {model.id: model for model in models}

        for model_id in preferred:
            model = by_id.get(model_id)
            if model and self._compatible(agent, model):
                return Assignment(agent.id, model.id)

        for model in models:
            if self._compatible(agent, model):
                return Assignment(agent.id, model.id)

        raise LookupError(f"No compatible model for agent: {agent.id}")

    @staticmethod
    def _compatible(agent: AgentContract, model: ModelSpec) -> bool:
        return not agent.capabilities or agent.capabilities.issubset(model.capabilities)
