"""Minimal executable VYRELON orchestration loop."""

from dataclasses import dataclass

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultVerifier
from core.contracts.work_unit import WorkUnit
from core.delegation import Delegation
from core.lifecycle import LifecycleCoordinator


@dataclass(frozen=True)
class OrchestrationResult:
    work_unit: WorkUnit
    delegation: Delegation
    output: object


class Orchestrator:
    """Coordinate delegation, execution, verification, and completion."""

    def __init__(self, lifecycle: LifecycleCoordinator | None = None) -> None:
        self.lifecycle = lifecycle or LifecycleCoordinator()

    def run(
        self,
        work_unit: WorkUnit,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        preferred_model_ids: list[str] | None = None,
        verifier: ResultVerifier | None = None,
    ) -> OrchestrationResult:
        delegation, output = self.lifecycle.run(
            work_unit,
            agent,
            models,
            executor,
            verifier,
            preferred_model_ids,
        )
        return OrchestrationResult(work_unit, delegation, output)
