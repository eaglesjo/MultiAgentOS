"""Minimal executable VYRELON orchestration loop."""

from dataclasses import dataclass
from collections.abc import Callable

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.work_unit import WorkUnit
from core.delegation import Delegation
from core.lifecycle import LifecycleCoordinator
from core.routing import RoutingStrategy


@dataclass(frozen=True)
class OrchestrationResult:
    work_unit: WorkUnit
    delegation: Delegation
    output: object


class Orchestrator:
    """Coordinate delegation, execution, verification, review, and completion."""

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
        reviewer: ResultReviewer | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        checkpoint: Callable[[WorkUnit], None] | None = None,
    ) -> OrchestrationResult:
        delegation, output = self.lifecycle.run(
            work_unit,
            agent,
            models,
            executor,
            verifier,
            reviewer,
            preferred_model_ids,
            routing_strategy,
            checkpoint=checkpoint,
        )
        return OrchestrationResult(work_unit, delegation, output)
