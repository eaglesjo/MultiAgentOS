"""Deterministic planning service for VYRELON."""

from core.contracts.planning import PlanStep, WorkPlan
from core.contracts.work_unit import WorkStatus, WorkUnit


class BasicPlanner:
    def plan(self, work_unit: WorkUnit, steps: list[PlanStep]) -> WorkPlan:
        work_unit.transition(WorkStatus.PLANNING)
        plan = WorkPlan(work_unit.id, work_unit.objective, tuple(steps))
        plan.validate()
        work_unit.metadata["plan_steps"] = [
            {
                "id": step.id,
                "objective": step.objective,
                "agent_id": step.agent_id,
                "depends_on": list(step.depends_on),
            }
            for step in plan.steps
        ]
        return plan
