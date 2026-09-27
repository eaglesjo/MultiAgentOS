"""Deterministic AI assignment and multi-AI routing."""

from dataclasses import dataclass
from enum import Enum

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from runtime.quota import QuotaSnapshot, quota_available, quota_score


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
        quota_snapshots = quota_snapshots or {}

        if strategy in {RoutingStrategy.EXPLICIT, RoutingStrategy.POOL}:
            for model_id in preferred:
                model = by_id.get(model_id)
                if model and self._compatible(agent, model):
                    snapshot = quota_snapshots.get(model.id)
                    if snapshot is None or quota_available(snapshot):
                        return Assignment(agent.id, model.id)
            if strategy is RoutingStrategy.EXPLICIT:
                raise LookupError(f"No explicitly assigned compatible model for agent: {agent.id}")

        if strategy in {RoutingStrategy.POOL, RoutingStrategy.AUTO}:
            compatible = [
                model for model in models
                if self._compatible(agent, model)
                and (
                    quota_snapshots.get(model.id) is None
                    or quota_available(quota_snapshots[model.id])
                )
            ]
            compatible.sort(
                key=lambda model: quota_score(quota_snapshots[model.id])
                if quota_snapshots.get(model.id) is not None else 0.5,
                reverse=True,
            )
            if compatible:
                return Assignment(agent.id, compatible[0].id)

        raise LookupError(f"No compatible model for agent: {agent.id}")

    @staticmethod
    def _compatible(agent: AgentContract, model: ModelSpec) -> bool:
        return not agent.capabilities or agent.capabilities.issubset(model.capabilities)
