"""Provider-neutral planning contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanStep:
    id: str
    objective: str
    agent_id: str | None = None
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkPlan:
    work_unit_id: str
    objective: str
    steps: tuple[PlanStep, ...]

    def validate(self) -> None:
        known = {step.id for step in self.steps}
        for step in self.steps:
            missing = set(step.depends_on) - known
            if missing:
                raise ValueError(f"Unknown plan dependencies: {sorted(missing)}")
