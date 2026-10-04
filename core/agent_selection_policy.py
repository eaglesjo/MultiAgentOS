"""Selection policy and fallback contracts for Agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.contracts.agent import AgentContract
from core.contracts.agent_selection import AgentCandidate, AgentPlan, StageConfidence
from core.contracts.evidence import EvidenceRecord
from core.contracts.work_unit import WorkUnit
from runtime.governance import specialist_route


@dataclass(frozen=True)
class SelectionDecision:
    """A proposed route from a secondary selector, before policy approval."""

    selected_agents: tuple[str, ...]
    confidence: float
    reasons: tuple[str, ...] = ()


class AgentSelectionStrategy(Protocol):
    def select_stage(
        self,
        *,
        work_unit: WorkUnit,
        evidence: tuple[EvidenceRecord, ...],
        candidates: tuple[AgentCandidate, ...],
        stage_index: int,
    ) -> SelectionDecision:
        ...

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
    """Hard boundary that a secondary selection strategy cannot bypass."""

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
        agents = []
        for agent_id in selected_agents:
            agent = registry.get(agent_id)
            agent.validate()
            agents.append(agent)

        expected = specialist_route(work_unit)
        if len(selected_agents) != len(expected):
            raise ValueError("selection policy requires the governed route length")
        for index, (expected_id, agent) in enumerate(zip(expected, agents, strict=True)):
            expected_agent = registry.get(expected_id)
            expected_agent.validate()
            if agent.id == expected_id:
                continue
            if expected_agent.kind != "specialist" or agent.kind != "specialist":
                raise ValueError(
                    f"selection policy does not permit replacing governed stage {index}: {expected_id}"
                )
        return selected_agents


class SelectionFallback:
    """Invoke a secondary selector only when deterministic confidence is low."""

    def __init__(self, strategy: AgentSelectionStrategy, *, policy: AgentSelectionPolicy | None = None):
        self.strategy = strategy
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

        stage_confidences = deterministic.stage_confidences
        ambiguous = tuple(
            stage
            for stage in stage_confidences
            if (
                self.policy.should_escalate(stage.score)
                and sum(
                    1
                    for candidate in deterministic.candidates
                    if stage.stage_index in candidate.stage_indices
                ) > 1
                and registry.get(stage.selected_agent_id).kind == "specialist"
            )
        )
        if not ambiguous:
            return deterministic

        select_stage = getattr(self.strategy, "select_stage", None)
        if select_stage is None:
            decision = self.strategy.select(
                work_unit=work_unit,
                evidence=deterministic.evidence,
                candidates=deterministic.candidates,
            )
        else:
            selected_by_stage = list(deterministic.selected_agents)
            reasons: list[str] = []
            confidence_values: list[float] = []
            candidate_pool = deterministic.candidates
            for stage in ambiguous:
                stage_candidates = tuple(
                    candidate
                    for candidate in candidate_pool
                    if stage.stage_index in candidate.stage_indices
                )
                decision = select_stage(
                    work_unit=work_unit,
                    evidence=deterministic.evidence,
                    candidates=stage_candidates,
                    stage_index=stage.stage_index,
                )
                if len(decision.selected_agents) != 1:
                    raise ValueError("stage selection must return exactly one Agent")
                selected_by_stage[stage.stage_index] = decision.selected_agents[0]
                reasons.extend(decision.reasons)
                confidence_values.append(decision.confidence)
            decision = SelectionDecision(
                selected_agents=tuple(selected_by_stage),
                confidence=(
                    sum(confidence_values) / len(confidence_values)
                    if confidence_values else deterministic.confidence
                ),
                reasons=tuple(reasons) or ("ambiguous stages were reselected",),
            )
        if not 0.0 <= decision.confidence <= 1.0:
            raise ValueError("selection strategy confidence must be between 0 and 1")

        candidate_map = {candidate.agent_id: candidate for candidate in deterministic.candidates}
        unknown = tuple(
            agent_id for agent_id in decision.selected_agents if agent_id not in candidate_map
        )
        if unknown:
            raise ValueError(
                "selection strategy returned Agent IDs outside the candidate pool: "
                + ", ".join(unknown)
            )
        for index, agent_id in enumerate(decision.selected_agents):
            if index not in candidate_map[agent_id].stage_indices:
                raise ValueError(
                    f"selection strategy assigned {agent_id} to incompatible stage {index}"
                )

        selected = self.policy.validate(
            work_unit,
            decision.selected_agents,
            registry,
        )
        candidates = tuple(
            AgentCandidate(
                agent_id=agent_id,
                score=decision.confidence,
                reasons=decision.reasons or ("secondary selection selected this route",),
                evidence_ids=tuple(record.id for record in deterministic.evidence),
                stage_indices=next(
                    candidate.stage_indices
                    for candidate in deterministic.candidates
                    if candidate.agent_id == agent_id
                ),
            )
            for agent_id in selected
        )
        stage_confidences = tuple(
            StageConfidence(
                stage_index=index,
                selected_agent_id=agent_id,
                selected_score=candidate_map[agent_id].score,
                best_score=max(
                    (
                        candidate.score
                        for candidate in deterministic.candidates
                        if index in candidate.stage_indices
                    ),
                    default=candidate_map[agent_id].score,
                ),
                margin=(
                    1.0
                    if sum(
                        1
                        for candidate in deterministic.candidates
                        if index in candidate.stage_indices
                    ) <= 1
                    else max(
                        0.0,
                        min(
                            1.0,
                            max(
                                (
                                    candidate.score
                                    for candidate in deterministic.candidates
                                    if index in candidate.stage_indices
                                ),
                                default=candidate_map[agent_id].score,
                            ) - max(
                                (
                                    candidate.score
                                    for candidate in deterministic.candidates
                                    if index in candidate.stage_indices
                                    and candidate.agent_id != agent_id
                                ),
                                default=0.0,
                            ),
                        ),
                    )
                ),
                evidence_coverage=(
                    sum(
                        1
                        for record in deterministic.evidence
                        if record.kind.value == "verified"
                    )
                    / max(1, len(deterministic.evidence))
                ),
            )
            for index, agent_id in enumerate(selected)
        )
        plan = AgentPlan(
            work_unit_id=work_unit.id,
            selected_agents=selected,
            route=selected,
            candidates=candidates,
            evidence=deterministic.evidence,
            confidence=decision.confidence,
            stage_confidences=stage_confidences,
            reasons=(
                "deterministic confidence below escalation threshold",
                *decision.reasons,
            ),
            policy_decisions=(
                f"secondary selection allowed below confidence {self.policy.confidence_threshold:.2f}",
                "route passed deterministic governance validation",
            ),
            selection_mode="hybrid",
        )
        plan.validate()
        return plan
