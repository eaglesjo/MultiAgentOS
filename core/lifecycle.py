"""Execution lifecycle coordinator for VYRELON."""

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultVerifier
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.delegation import Delegation, DelegationEngine


class LifecycleError(RuntimeError):
    """Raised when execution or verification cannot complete successfully."""


class LifecycleCoordinator:
    """Run delegated work through execution and verification."""

    def __init__(self, delegation: DelegationEngine | None = None) -> None:
        self.delegation = delegation or DelegationEngine()

    def run(
        self,
        work_unit: WorkUnit,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier | None = None,
        preferred_model_ids: list[str] | None = None,
    ) -> tuple[Delegation, object]:
        delegation = self.delegation.delegate(
            work_unit, agent, models, preferred_model_ids
        )
        try:
            output = executor.execute(
                agent=agent,
                model_id=delegation.assignment.model_id,
                work_unit=work_unit,
            )
            if verifier is not None:
                work_unit.transition(WorkStatus.VERIFYING)
                if not verifier.verify(work_unit=work_unit, output=output):
                    work_unit.transition(WorkStatus.FAILED)
                    raise LifecycleError(f"Verification failed for work unit: {work_unit.id}")
            work_unit.transition(WorkStatus.COMPLETED)
            return delegation, output
        except Exception:
            if work_unit.status not in {WorkStatus.FAILED, WorkStatus.COMPLETED}:
                work_unit.transition(WorkStatus.FAILED)
            raise
