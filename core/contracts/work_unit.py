"""Provider-neutral work unit contract for VYRELON."""

from dataclasses import dataclass, field
from enum import Enum


class WorkStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    REVIEWING = "reviewing"
    WAITING_HUMAN_APPROVAL = "waiting_human_approval"
    HANDOFF = "handoff"
    COMPLETED = "completed"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[WorkStatus, frozenset[WorkStatus]] = {
    WorkStatus.PENDING: frozenset({WorkStatus.PLANNING, WorkStatus.EXECUTING, WorkStatus.FAILED}),
    WorkStatus.PLANNING: frozenset({WorkStatus.EXECUTING, WorkStatus.FAILED}),
    WorkStatus.EXECUTING: frozenset({WorkStatus.VERIFYING, WorkStatus.COMPLETED, WorkStatus.FAILED}),
    WorkStatus.VERIFYING: frozenset({WorkStatus.EXECUTING, WorkStatus.REVIEWING, WorkStatus.HANDOFF, WorkStatus.COMPLETED, WorkStatus.FAILED}),
    WorkStatus.REVIEWING: frozenset({WorkStatus.EXECUTING, WorkStatus.WAITING_HUMAN_APPROVAL, WorkStatus.HANDOFF, WorkStatus.COMPLETED, WorkStatus.FAILED}),
    WorkStatus.WAITING_HUMAN_APPROVAL: frozenset({WorkStatus.EXECUTING, WorkStatus.HANDOFF, WorkStatus.COMPLETED, WorkStatus.FAILED}),
    WorkStatus.HANDOFF: frozenset({WorkStatus.EXECUTING, WorkStatus.COMPLETED, WorkStatus.FAILED}),
    WorkStatus.COMPLETED: frozenset(),
    WorkStatus.FAILED: frozenset(),
}


@dataclass
class WorkUnit:
    id: str
    objective: str
    status: WorkStatus = WorkStatus.PENDING
    inputs: dict[str, object] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    assigned_agents: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def assign(self, agent_id: str) -> None:
        if agent_id not in self.assigned_agents:
            self.assigned_agents.append(agent_id)

    def transition(self, status: WorkStatus) -> None:
        if status == self.status:
            return
        if status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(
                f"Invalid WorkUnit transition: {self.status.value} -> {status.value}"
            )
        self.status = status
