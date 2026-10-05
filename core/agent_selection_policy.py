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
class CandidatePoolExpansionPolicy:
    """Expand specialist candidates only when the deterministic pool is too small."""

    min_candidates: int = 2
    top_k: int = 4
    profile_by_platform: tuple[tuple[str, str], ...] = (
        ("react-native", "react-native"),
        ("android", "android-native"),
        ("ios", "ios-native"),
    )

    def __post_init__(self) -> None:
        if self.min_candidates < 1:
            raise ValueError("candidate pool min_candidates must be at least 1")
        if self.top_k < self.min_candidates:
            raise ValueError("candidate pool top_k must be >= min_candidates")

    def profile_for(self, work_unit: WorkUnit) -> str | None:
        platform = (work_unit.target or str(work_unit.metadata.get("platform", ""))).strip().lower()
        return dict(self.profile_by_platform).get(platform)


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
        """Merge model decisions into only the ambiguous deterministic stages."""
        stage_confidences = deterministic.stage_confidences
        if not stage_confidences and not self.policy.should_escalate(deterministic.confidence):
            return deterministic

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

        selected_by_stage = list(deterministic.selected_agents)
        model_confidence_by_stage: dict[int, float] = {}
        model_reasons: list[str] = []
        select_stage = getattr(self.strategy, "select_stage", None)

        if select_stage is not None:
            for stage in ambiguous:
                stage_candidates = tuple(
                    candidate
                    for candidate in deterministic.candidates
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
                if not 0.0 <= decision.confidence <= 1.0:
                    raise ValueError("selection strategy confidence must be between 0 and 1")
                selected_by_stage[stage.stage_index] = decision.selected_agents[0]
                model_confidence_by_stage[stage.stage_index] = decision.confidence
                model_reasons.extend(decision.reasons)
        else:
            decision = self.strategy.select(
                work_unit=work_unit,
                evidence=deterministic.evidence,
                candidates=deterministic.candidates,
            )
            if len(decision.selected_agents) != len(deterministic.selected_agents):
                raise ValueError(
                    "legacy selection strategy must return the complete governed route"
                )
            if not 0.0 <= decision.confidence <= 1.0:
                raise ValueError("selection strategy confidence must be between 0 and 1")
            changed = {
                index
                for index, (before, after) in enumerate(
                    zip(deterministic.selected_agents, decision.selected_agents, strict=True)
                )
                if before != after
            }
            ambiguous_indices = {stage.stage_index for stage in ambiguous}
            if not changed.issubset(ambiguous_indices):
                raise ValueError(
                    "selection strategy may only change ambiguous specialist stages"
                )
            selected_by_stage = list(decision.selected_agents)
            for stage in ambiguous:
                model_confidence_by_stage[stage.stage_index] = decision.confidence
            model_reasons.extend(decision.reasons)

        selected_ids = tuple(selected_by_stage)
        candidate_map = {
            candidate.agent_id: candidate for candidate in deterministic.candidates
        }
        unknown = tuple(agent_id for agent_id in selected_ids if agent_id not in candidate_map)
        if unknown:
            raise ValueError(
                "selection strategy returned Agent IDs outside the candidate pool: "
                + ", ".join(unknown)
            )
        for index, agent_id in enumerate(selected_ids):
            if index not in candidate_map[agent_id].stage_indices:
                raise ValueError(
                    f"selection strategy assigned {agent_id} to incompatible stage {index}"
                )

        selected = self.policy.validate(
            work_unit,
            selected_ids,
            registry,
        )

        merged_stage_confidences = tuple(
            StageConfidence(
                stage_index=stage.stage_index,
                selected_agent_id=selected[stage.stage_index],
                selected_score=candidate_map[selected[stage.stage_index]].score,
                best_score=stage.best_score,
                margin=stage.margin,
                evidence_coverage=stage.evidence_coverage,
                selection_source=(
                    "model" if stage.stage_index in model_confidence_by_stage else stage.selection_source
                ),
                model_confidence=model_confidence_by_stage.get(stage.stage_index),
            )
            for stage in stage_confidences
        )
        plan = AgentPlan(
            work_unit_id=work_unit.id,
            selected_agents=selected,
            route=selected,
            candidates=deterministic.candidates,
            evidence=deterministic.evidence,
            confidence=(
                sum(model_confidence_by_stage.values())
                / len(model_confidence_by_stage)
                if model_confidence_by_stage
                else deterministic.confidence
            ),
            stage_confidences=merged_stage_confidences,
            reasons=(
                "deterministic confidence below escalation threshold",
                "only ambiguous specialist stages were reselected",
                *tuple(model_reasons),
            ),
            policy_decisions=(
                f"secondary selection allowed below confidence {self.policy.confidence_threshold:.2f}",
                "deterministic candidate pool preserved during merge",
                "route passed deterministic governance validation",
            ),
            selection_mode="hybrid",
        )
        plan.validate()
        return plan
