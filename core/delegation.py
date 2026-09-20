"""Agent delegation engine for VYRELON."""

from dataclasses import dataclass

from core.contracts.agent import AgentContract
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.routing import AIRouter, Assignment
from core.contracts.ai import ModelSpec


@dataclass(frozen=True)
class Delegation:
    work_unit_id: str
    agent_id: str
    assignment: Assignment


class DelegationEngine:
    def __init__(self, router: AIRouter | None = None) -> None:
        self.router = router or AIRouter()

    def delegate(
        self,
        work_unit: WorkUnit,
        agent: AgentContract,
        models: list[ModelSpec],
        preferred_model_ids: list[str] | None = None,
    ) -> Delegation:
        # Resolve the model before mutating WorkUnit state. A routing failure
        # must not leave a work unit pretending that execution has started.
        assignment = self.router.assign(agent, models, preferred_model_ids)
        work_unit.assign(agent.id)
        work_unit.transition(WorkStatus.EXECUTING)
        return Delegation(work_unit.id, agent.id, assignment)
