"""Execution lifecycle coordinator for VYRELON."""

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.delegation import Delegation, DelegationEngine
from core.routing import RoutingStrategy
from collections.abc import Callable


class LifecycleError(RuntimeError):
    """Raised when execution, verification, or review cannot complete successfully."""


class LifecycleCoordinator:
    """Run delegated work through execution, verification, review, and completion."""

    def __init__(self, delegation: DelegationEngine | None = None) -> None:
        self.delegation = delegation or DelegationEngine()

    def run(
        self,
        work_unit: WorkUnit,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        checkpoint: Callable[[WorkUnit], None] | None = None,
    ) -> tuple[Delegation, object]:
        delegation = self.delegation.delegate(
            work_unit, agent, models, preferred_model_ids, routing_strategy
        )
        try:
            if checkpoint is not None:
                checkpoint(work_unit)
            output = executor.execute(
                agent=agent,
                model_id=delegation.assignment.model_id,
                work_unit=work_unit,
            )
            if verifier is not None:
                work_unit.transition(WorkStatus.VERIFYING)
                if checkpoint is not None:
                    checkpoint(work_unit)
                if not verifier.verify(work_unit=work_unit, output=output):
                    work_unit.transition(WorkStatus.FAILED)
                    raise LifecycleError(f"Verification failed for work unit: {work_unit.id}")
            if reviewer is not None:
                if work_unit.status != WorkStatus.VERIFYING:
                    work_unit.transition(WorkStatus.VERIFYING)
                work_unit.transition(WorkStatus.REVIEWING)
                if checkpoint is not None:
                    checkpoint(work_unit)
                decision = reviewer.review(work_unit=work_unit, output=output)
                if not decision.approved:
                    work_unit.transition(WorkStatus.FAILED)
                    raise LifecycleError(f"Review rejected work unit: {work_unit.id}")
            if verifier is not None or reviewer is not None:
                work_unit.transition(WorkStatus.HANDOFF)
                if checkpoint is not None:
                    checkpoint(work_unit)
                work_unit.transition(WorkStatus.COMPLETED)
            else:
                work_unit.transition(WorkStatus.COMPLETED)
            if checkpoint is not None:
                checkpoint(work_unit)
            return delegation, output
        except Exception:
            if work_unit.status not in {WorkStatus.FAILED, WorkStatus.COMPLETED}:
                work_unit.transition(WorkStatus.FAILED)
                if checkpoint is not None:
                    checkpoint(work_unit)
            raise
