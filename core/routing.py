from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.health import ModelHealth
from core.contracts.quota import QuotaSnapshot
if TYPE_CHECKING:
    from runtime.capability import CapabilityRegistry


class RoutingStrategy(str, Enum):
    EXPLICIT = "explicit"
    POOL = "pool"
    AUTO = "auto"


@dataclass(frozen=True)
class Assignment:
    agent_id: str
    model_id: str


@dataclass(frozen=True)
class RoutingCandidate:
    model_id: str
    provider_id: str
    selected: bool
    compatible: bool
    health_available: bool
    quota_available: bool
    capability_score: float
    quota_score: float
    missing_capabilities: frozenset[str]
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class RoutingExplanation:
    agent_id: str
    strategy: RoutingStrategy
    selected_model_id: str | None
    candidates: tuple[RoutingCandidate, ...]

    @property
    def assignment(self) -> Assignment:
        if self.selected_model_id is None:
            raise LookupError(f"No compatible available model for agent: {self.agent_id}")
        return Assignment(self.agent_id, self.selected_model_id)


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
        return self.explain(
            agent,
            models,
            preferred_model_ids=preferred_model_ids,
            strategy=strategy,
            quota_snapshots=quota_snapshots,
            health_snapshots=health_snapshots,
            capability_registry=capability_registry,
        ).assignment

    def explain(
        self,
        agent: AgentContract,
        models: list[ModelSpec],
        preferred_model_ids: list[str] | None = None,
        strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        quota_snapshots: dict[str, QuotaSnapshot] | None = None,
        health_snapshots: dict[str, ModelHealth] | None = None,
        capability_registry: CapabilityRegistry | None = None,
    ) -> RoutingExplanation:
        """Explain model eligibility, rejection reasons, and the selected model."""
        from runtime.quota import quota_available, quota_score

        strategy = RoutingStrategy(strategy)
        preferred = preferred_model_ids if preferred_model_ids is not None else list(agent.model_ids)
        preferred_set = set(preferred)
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

        candidates = []
        for model in models:
            _, missing, cap_score = capability_match(model)
            health = health_snapshots.get(model.id)
            health_ok = health is None or health.available
            quota = quota_snapshots.get(model.id)
            quota_ok = quota is None or quota_available(quota)
            reasons = []
            if missing:
                reasons.append("missing_capabilities")
            if not health_ok:
                reasons.append("unhealthy")
            if not quota_ok:
                reasons.append("quota_unavailable")
            if strategy is RoutingStrategy.EXPLICIT and model.id not in preferred_set:
                reasons.append("not_explicitly_selected")
            candidates.append(
                RoutingCandidate(
                    model_id=model.id,
                    provider_id=model.provider_id,
                    selected=False,
                    compatible=not missing,
                    health_available=health_ok,
                    quota_available=quota_ok,
                    capability_score=cap_score,
                    quota_score=quota_score(quota) if quota is not None else 0.5,
                    missing_capabilities=frozenset(missing),
                    rejection_reasons=tuple(reasons),
                )
            )

        by_id = {model.id: model for model in models}
        selected_model_id = None

        if strategy in {RoutingStrategy.EXPLICIT, RoutingStrategy.POOL}:
            for model_id in preferred:
                model = by_id.get(model_id)
                if model is None:
                    continue
                candidate = next(item for item in candidates if item.model_id == model.id)
                if candidate.compatible and candidate.health_available and candidate.quota_available:
                    selected_model_id = model.id
                    break
            if selected_model_id is None and strategy is RoutingStrategy.EXPLICIT:
                raise LookupError(f"No explicitly assigned available model for agent: {agent.id}")

        if selected_model_id is None and strategy in {RoutingStrategy.POOL, RoutingStrategy.AUTO}:
            eligible = [
                item for item in candidates
                if item.compatible and item.health_available and item.quota_available
            ]
            eligible.sort(
                key=lambda item: (item.capability_score, item.quota_score),
                reverse=True,
            )
            if eligible:
                selected_model_id = eligible[0].model_id

        if selected_model_id is None:
            raise LookupError(f"No compatible available model for agent: {agent.id}")

        explained = tuple(
            RoutingCandidate(
                model_id=item.model_id,
                provider_id=item.provider_id,
                selected=item.model_id == selected_model_id,
                compatible=item.compatible,
                health_available=item.health_available,
                quota_available=item.quota_available,
                capability_score=item.capability_score,
                quota_score=item.quota_score,
                missing_capabilities=item.missing_capabilities,
                rejection_reasons=tuple(
                    reason for reason in item.rejection_reasons
                    if reason != "not_explicitly_selected" or item.model_id != selected_model_id
                ),
            )
            for item in candidates
        )
        return RoutingExplanation(
            agent_id=agent.id,
            strategy=strategy,
            selected_model_id=selected_model_id,
            candidates=explained,
        )

    @staticmethod
    def compatible(agent: AgentContract, model: ModelSpec) -> bool:
        return not agent.capabilities or agent.capabilities.issubset(model.capabilities)

    _compatible = compatible
