"""Deterministic AI assignment and multi-AI routing."""

from dataclasses import dataclass
from enum import Enum

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.health import ModelHealth
from core.contracts.quota import QuotaSnapshot
from runtime.capability import CapabilityRegistry
from runtime.quota import quota_available, quota_score


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
        quota_snapshots: dict[str, QuotaSnapshot] | None = None,
        health_snapshots: dict[str, ModelHealth] | None = None,
        capability_registry: CapabilityRegistry | None = None,
    ) -> Assignment:
        strategy = RoutingStrategy(strategy)
        preferred = preferred_model_ids if preferred_model_ids is not None else list(agent.model_ids)
        by_id = {model.id: model for model in models}
        quota_snapshots = quota_snapshots or {}
        health_snapshots = health_snapshots or {}
        requirements = frozenset(agent.capabilities)

        def capability_match(model: ModelSpec):
            if capability_registry is None:
                matched = requirements & model.capabilities
                return matched, requirements - model.capabilities, (
                    len(matched) / len(requirements) if requirements else 1.0
                )
            match = capability_registry.match(model, requirements)
            return match.matched, match.missing, match.score

        def available(model: ModelSpec) -> bool:
            health = health_snapshots.get(model.id)
            _, missing, _ = capability_match(model)
            return (
                not missing
                and (health is None or health.available)
                and (
                    quota_snapshots.get(model.id) is None
                    or quota_available(quota_snapshots[model.id])
                )
            )

        if strategy in {RoutingStrategy.EXPLICIT, RoutingStrategy.POOL}:
            for model_id in preferred:
                model = by_id.get(model_id)
                if model and available(model):
                    return Assignment(agent.id, model.id)
            if strategy is RoutingStrategy.EXPLICIT:
                raise LookupError(f"No explicitly assigned available model for agent: {agent.id}")

        if strategy in {RoutingStrategy.POOL, RoutingStrategy.AUTO}:
            compatible = [model for model in models if available(model)]
            compatible.sort(
                key=lambda model: (
                    capability_match(model)[2],
                    quota_score(quota_snapshots[model.id])
                    if quota_snapshots.get(model.id) is not None else 0.5,
                ),
                reverse=True,
            )
            if compatible:
                return Assignment(agent.id, compatible[0].id)

        raise LookupError(f"No compatible available model for agent: {agent.id}")

    @staticmethod
    def compatible(agent: AgentContract, model: ModelSpec) -> bool:
        return not agent.capabilities or agent.capabilities.issubset(model.capabilities)

    _compatible = compatible
