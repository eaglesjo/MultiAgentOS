"""Deterministic AI assignment and multi-AI routing."""

from dataclasses import dataclass
from enum import Enum

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec


class RoutingStrategy(str, Enum):
    EXPLICIT = "explicit"
    POOL = "pool"
    AUTO = "auto"


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
        strategy: RoutingStrategy | str = RoutingStrategy.POOL,
    ) -> Assignment:
        strategy = RoutingStrategy(strategy)
        preferred = preferred_model_ids if preferred_model_ids is not None else list(agent.model_ids)
        by_id = {model.id: model for model in models}

        if strategy in {RoutingStrategy.EXPLICIT, RoutingStrategy.POOL}:
            for model_id in preferred:
                model = by_id.get(model_id)
                if model and self._compatible(agent, model):
                    return Assignment(agent.id, model.id)
            if strategy is RoutingStrategy.EXPLICIT:
                raise LookupError(f"No explicitly assigned compatible model for agent: {agent.id}")

        if strategy in {RoutingStrategy.POOL, RoutingStrategy.AUTO}:
            for model in models:
                if self._compatible(agent, model):
                    return Assignment(agent.id, model.id)

        raise LookupError(f"No compatible model for agent: {agent.id}")

    @staticmethod
    def _compatible(agent: AgentContract, model: ModelSpec) -> bool:
        return not agent.capabilities or agent.capabilities.issubset(model.capabilities)
