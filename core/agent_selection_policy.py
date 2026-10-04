"""Selection policy and fallback contracts for Agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.contracts.agent import AgentContract
from core.contracts.agent_selection import AgentCandidate, AgentPlan
from core.contracts.evidence import EvidenceRecord
from core.contracts.work_unit import WorkUnit
from runtime.governance import specialist_route, validate_specialist_route


@dataclass(frozen=True)
class SelectionDecision:
    """A proposed route from a secondary selector, before policy approval."""

    selected_agents: tuple[str, ...]
    confidence: float
    reasons: tuple[str, ...] = ()


class LLMSelector(Protocol):
    def select(
        self,
        *,
        work_unit: WorkUnit,
        evidence: tuple[EvidenceRecord, ...],
        candidates: tuple[AgentCandidate, ...],
    ) -> SelectionDecision:
        ...


@dataclass(frozen=True)
class AgentSelectionPolicy:
    """Hard boundary that an LLM selector cannot bypass."""

    confidence_threshold: float = 0.75
    min_confidence: float = 0.0

    def should_escalate(self, confidence: float) -> bool:
        return confidence < self.confidence_threshold

    def validate(
        self,
        work_unit: WorkUnit,
        selected_agents: tuple[str, ...],
        registry,
    ) -> tuple[str, ...]:
        if not selected_agents:
            raise ValueError("selection policy requires at least one Agent")
        for agent_id in selected_agents:
            agent = registry.get(agent_id)
            agent.validate()
            if agent.kind == "governance":
                raise ValueError(
                    f"selection policy cannot select governance agent as specialist route: {agent_id}"
                )

        try:
            check = validate_specialist_route(work_unit, selected_agents)
        except ValueError as exc:
            raise ValueError(f"selection policy rejected route: {exc}") from exc
        if not check.passed:
            raise ValueError(
                "selection policy rejected route: " + "; ".join(check.findings)
            )
        return selected_agents


class LLMFallbackSelector:
    """Invoke a secondary selector only when deterministic confidence is low."""

    def __init__(self, selector: LLMSelector, *, policy: AgentSelectionPolicy | None = None):
        self.selector = selector
        self.policy = policy or AgentSelectionPolicy()

    def select(
        self,
        *,
        work_unit: WorkUnit,
        deterministic: AgentPlan,
        registry,
    ) -> AgentPlan:
        if not self.policy.should_escalate(deterministic.confidence):
            return deterministic

        decision = self.selector.select(
            work_unit=work_unit,
            evidence=deterministic.evidence,
            candidates=deterministic.candidates,
        )
        if not 0.0 <= decision.confidence <= 1.0:
            raise ValueError("LLM selector confidence must be between 0 and 1")

        selected = self.policy.validate(
            work_unit,
            decision.selected_agents,
            registry,
        )
        candidates = tuple(
            AgentCandidate(
                agent_id=agent_id,
                score=decision.confidence,
                reasons=decision.reasons or ("LLM fallback selected this route",),
                evidence_ids=tuple(record.id for record in deterministic.evidence),
            )
            for agent_id in selected
        )
        plan = AgentPlan(
            work_unit_id=work_unit.id,
            selected_agents=selected,
            route=selected,
            candidates=candidates,
            evidence=deterministic.evidence,
            confidence=decision.confidence,
            reasons=(
                "deterministic confidence below escalation threshold",
                *decision.reasons,
            ),
            policy_decisions=(
                f"LLM fallback allowed below confidence {self.policy.confidence_threshold:.2f}",
                "route passed deterministic governance validation",
            ),
            selection_mode="hybrid",
        )
        plan.validate()
        return plan
