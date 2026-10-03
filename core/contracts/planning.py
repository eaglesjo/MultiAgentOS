"""Provider-neutral planning contracts."""

from dataclasses import dataclass

from core.contracts.scope import ScopeLock


@dataclass(frozen=True)
class PlanStep:
    id: str
    objective: str
    agent_id: str | None = None
    depends_on: tuple[str, ...] = ()
    scope_lock: ScopeLock = ScopeLock()


@dataclass(frozen=True)
class WorkPlan:
    work_unit_id: str
    objective: str
    steps: tuple[PlanStep, ...]

    def validate(self) -> None:
        known = {step.id for step in self.steps}
        for step in self.steps:
            step.scope_lock.validate()
        for step in self.steps:
            missing = set(step.depends_on) - known
            if missing:
                raise ValueError(f"Unknown plan dependencies: {sorted(missing)}")
