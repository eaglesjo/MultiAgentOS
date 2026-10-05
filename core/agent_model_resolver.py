"""Explicit Agent x Model resolution contract."""

from __future__ import annotations

from dataclasses import dataclass

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.routing import AIRouter, Assignment, RoutingExplanation, RoutingStrategy
from runtime.capability import CapabilityRegistry


@dataclass(frozen=True)
class AgentModelResolution:
    """Resolved executable model for an Agent, with an auditable explanation."""
    agent_id: str
    model_id: str
    assignment: Assignment
    explanation: RoutingExplanation


class AgentModelResolver:
    """Resolve an Agent to a compatible, available model."""

    def __init__(self, router: AIRouter | None = None) -> None:
        self.router = router or AIRouter()

    def resolve(self, agent: AgentContract, models: list[ModelSpec], *,
                capability_registry: CapabilityRegistry | None = None,
                preferred_model_ids: list[str] | None = None,
                strategy: RoutingStrategy | str = RoutingStrategy.POOL,
                quota_snapshots=None, health_snapshots=None) -> AgentModelResolution:
        allowed = self._allowed_models(agent, models)
        if not allowed:
            raise LookupError(f"No models allowed for agent: {agent.id}")
        explanation = self.router.explain(
            agent, allowed, preferred_model_ids=preferred_model_ids,
            strategy=strategy, quota_snapshots=quota_snapshots,
            health_snapshots=health_snapshots,
            capability_registry=capability_registry,
        )
        assignment = explanation.assignment
        return AgentModelResolution(agent.id, assignment.model_id, assignment, explanation)

    @staticmethod
    def _allowed_models(agent: AgentContract, models: list[ModelSpec]) -> list[ModelSpec]:
        if not agent.model_ids:
            return list(models)
        allowed = set(agent.model_ids)
        return [model for model in models if model.id in allowed]
