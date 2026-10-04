"""Provider-neutral work unit contract for AGENT_EXECUTION_RUNTIME."""

from dataclasses import dataclass, field
from enum import Enum

from core.contracts.scope import ScopeLock


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
    READY_FOR_APPROVAL = "ready_for_approval"
    USER_APPROVED = "user_approved"
    RELEASED = "released"
    HOLD = "hold"
    BLOCKED = "blocked"


_ALLOWED_TRANSITIONS: dict[WorkStatus, frozenset[WorkStatus]] = {
    WorkStatus.PENDING: frozenset({WorkStatus.PLANNING, WorkStatus.EXECUTING, WorkStatus.FAILED, WorkStatus.HOLD}),
    WorkStatus.PLANNING: frozenset({WorkStatus.EXECUTING, WorkStatus.FAILED, WorkStatus.HOLD}),
    WorkStatus.EXECUTING: frozenset({WorkStatus.VERIFYING, WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.HOLD}),
    WorkStatus.VERIFYING: frozenset({WorkStatus.EXECUTING, WorkStatus.REVIEWING, WorkStatus.HANDOFF, WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.HOLD}),
    WorkStatus.REVIEWING: frozenset({WorkStatus.EXECUTING, WorkStatus.READY_FOR_APPROVAL, WorkStatus.WAITING_HUMAN_APPROVAL, WorkStatus.HANDOFF, WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.HOLD}),
    WorkStatus.WAITING_HUMAN_APPROVAL: frozenset({WorkStatus.EXECUTING, WorkStatus.HANDOFF, WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.HOLD}),
    WorkStatus.READY_FOR_APPROVAL: frozenset({WorkStatus.USER_APPROVED, WorkStatus.EXECUTING, WorkStatus.FAILED, WorkStatus.HOLD}),
    WorkStatus.USER_APPROVED: frozenset({WorkStatus.RELEASED, WorkStatus.FAILED, WorkStatus.HOLD}),
    WorkStatus.RELEASED: frozenset({WorkStatus.COMPLETED}),
    WorkStatus.HANDOFF: frozenset({WorkStatus.EXECUTING, WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.HOLD}),
    WorkStatus.COMPLETED: frozenset({WorkStatus.READY_FOR_APPROVAL, WorkStatus.BLOCKED}),
    WorkStatus.FAILED: frozenset({WorkStatus.EXECUTING}),
    WorkStatus.HOLD: frozenset({WorkStatus.BLOCKED, WorkStatus.FAILED, WorkStatus.EXECUTING}),
    WorkStatus.BLOCKED: frozenset(),
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
    work_type: str = "development"
    target: str = ""
    environment: str = ""
    artifact_class: str = ""
    release_impact: str = "none"
    scope_lock: ScopeLock = field(default_factory=ScopeLock)
    hold_reason: str = ""

    def assign(self, agent_id: str) -> None:
        if agent_id not in self.assigned_agents:
            self.assigned_agents.append(agent_id)

    def hold(self, reason: str) -> None:
        if not reason.strip():
            raise ValueError("HOLD requires a reason")
        self.hold_reason = reason
        self.transition(WorkStatus.HOLD)

    def resume_from_hold(self, *, authorized: bool = False) -> None:
        if self.status is not WorkStatus.HOLD:
            raise ValueError("WorkUnit is not on HOLD")
        if not authorized:
            raise PermissionError("HOLD resume requires explicit authorization")
        self.hold_reason = ""
        self.transition(WorkStatus.EXECUTING)

    def transition(self, status: WorkStatus) -> None:
        if status == self.status:
            return
        self.scope_lock.validate()
        if status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(
                f"Invalid WorkUnit transition: {self.status.value} -> {status.value}"
            )
        if (
            self.status is WorkStatus.COMPLETED
            and status is WorkStatus.READY_FOR_APPROVAL
            and (
                self.release_impact == "none"
                or self.metadata.get("released") is True
            )
        ):
            raise ValueError(
                "only unreleased release-impacting work may enter approval gating"
            )
        self.status = status
