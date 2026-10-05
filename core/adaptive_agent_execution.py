"""Adaptive execution loop for governed Agent plans.

The loop is intentionally provider-neutral: an executor reports stage outcomes,
and the selector decides whether a failed/low-confidence specialist stage should
be reselected. Governance remains the final authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from core.agent_selection_policy import SelectionFallback
from core.contracts.agent_selection import AgentPlan
from core.contracts.evidence import EvidenceRecord
from core.contracts.work_unit import WorkStatus, WorkUnit


@dataclass(frozen=True)
class StageExecutionOutcome:
    """Auditable outcome of executing one route stage."""

    stage_index: int
    agent_id: str
    success: bool
    confidence: float
    evidence: tuple[EvidenceRecord, ...] = ()
    reason: str = ""

    def validate(self) -> None:
        if self.stage_index < 0:
            raise ValueError("stage execution stage_index must be non-negative")
        if not self.agent_id.strip():
            raise ValueError("stage execution agent_id must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("stage execution confidence must be between 0 and 1")
        for record in self.evidence:
            record.validate()


@dataclass(frozen=True)
class ExecutionRound:
    """One plan/execution/evidence cycle."""

    attempt: int
    plan: AgentPlan
    outcomes: tuple[StageExecutionOutcome, ...]

    @property
    def success(self) -> bool:
        return bool(self.outcomes) and all(item.success for item in self.outcomes)

    def validate(self) -> None:
        if self.attempt < 1:
            raise ValueError("execution attempt must be at least 1")
        self.plan.validate()
        for outcome in self.outcomes:
            outcome.validate()


@dataclass(frozen=True)
class AdaptiveExecutionPolicy:
    """Bounds adaptive reselection and defines escalation conditions."""

    max_attempts: int = 2
    retry_confidence_threshold: float = 0.70

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if not 0.0 <= self.retry_confidence_threshold <= 1.0:
            raise ValueError("retry confidence threshold must be between 0 and 1")


class StageExecutor(Protocol):
    def execute(
        self,
        *,
        work_unit: WorkUnit,
        plan: AgentPlan,
        stage_indices: tuple[int, ...],
    ) -> tuple[StageExecutionOutcome, ...]:
        ...


class AdaptiveAgentExecutionLoop:
    """Execute a governed plan and reselect only failed/low-confidence specialists."""

    def __init__(
        self,
        *,
        selector,
        registry,
        executor: StageExecutor,
        selection_fallback: SelectionFallback | None = None,
        policy: AdaptiveExecutionPolicy | None = None,
    ) -> None:
        self.selector = selector
        self.registry = registry
        self.executor = executor
        self.selection_fallback = selection_fallback
        self.policy = policy or AdaptiveExecutionPolicy()

    def _retryable_stages(
        self,
        plan: AgentPlan,
        outcomes: tuple[StageExecutionOutcome, ...],
    ) -> tuple[int, ...]:
        outcome_by_stage = {item.stage_index: item for item in outcomes}
        retryable: list[int] = []
        for stage in plan.stage_confidences:
            outcome = outcome_by_stage.get(stage.stage_index)
            if outcome is None or stage.stage_index >= len(plan.route):
                continue
            agent = self.registry.get(stage.selected_agent_id)
            if agent.kind != "specialist":
                continue
            if not outcome.success or outcome.confidence < self.policy.retry_confidence_threshold:
                retryable.append(stage.stage_index)
        return tuple(retryable)

    def run(
        self,
        *,
        work_unit: WorkUnit,
        initial_plan: AgentPlan,
    ) -> tuple[ExecutionRound, ...]:
        initial_plan.validate()
        rounds: list[ExecutionRound] = []
        plan = initial_plan

        for attempt in range(1, self.policy.max_attempts + 1):
            if attempt == 1:
                stage_indices = tuple(range(len(plan.route)))
            else:
                stage_indices = retryable
            work_unit.metadata["execution_attempt"] = attempt
            outcomes = self.executor.execute(
                work_unit=work_unit,
                plan=plan,
                stage_indices=stage_indices,
            )
            current = ExecutionRound(attempt=attempt, plan=plan, outcomes=outcomes)
            current.validate()
            rounds.append(current)

            if current.success:
                return tuple(rounds)

            retryable = self._retryable_stages(plan, outcomes)
            if not retryable or attempt == self.policy.max_attempts:
                return tuple(rounds)

            if self.selection_fallback is None:
                return tuple(rounds)

            if work_unit.status is WorkStatus.FAILED:
                work_unit.transition(WorkStatus.EXECUTING)

            # Execution evidence is fed back only to the stages that failed or
            # produced low-confidence output; the route remains policy-governed.
            execution_evidence = tuple(
                record
                for outcome in outcomes
                if outcome.stage_index in retryable
                for record in outcome.evidence
            )
            merged_evidence = tuple(
                dict.fromkeys((*plan.evidence, *execution_evidence))
            )
            deterministic = self.selector.select(
                work_unit,
                evidence=merged_evidence,
            ).plan
            plan = self.selection_fallback.select(
                work_unit=work_unit,
                deterministic=deterministic,
                registry=self.registry,
            )

        return tuple(rounds)
