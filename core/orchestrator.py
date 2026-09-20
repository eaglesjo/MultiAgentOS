"""Minimal executable VYRELON orchestration loop."""

from dataclasses import dataclass

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.delegation import Delegation, DelegationEngine


@dataclass(frozen=True)
class OrchestrationResult:
    work_unit: WorkUnit
    delegation: Delegation
    output: object


class Orchestrator:
    """Coordinate work assignment without coupling to a model vendor."""

    def __init__(self, delegation: DelegationEngine | None = None) -> None:
        self.delegation = delegation or DelegationEngine()

    def run(self, work_unit: WorkUnit, agent: AgentContract,
            models: list[ModelSpec], executor,
            preferred_model_ids: list[str] | None = None) -> OrchestrationResult:
        delegation = self.delegation.delegate(
            work_unit, agent, models, preferred_model_ids
        )
        try:
            output = executor.execute(
                agent=agent,
                model_id=delegation.assignment.model_id,
                work_unit=work_unit,
            )
        except Exception:
            work_unit.transition(WorkStatus.FAILED)
            raise
        work_unit.transition(WorkStatus.COMPLETED)
        return OrchestrationResult(work_unit, delegation, output)
