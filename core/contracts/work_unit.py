"""Provider-neutral work unit contract for VYRELON."""

from dataclasses import dataclass, field
from enum import Enum


class WorkStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


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
        self.status = status
