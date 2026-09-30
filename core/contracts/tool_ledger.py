"""Durable tool invocation ledger contracts."""
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .replay import ReplayPolicy


class ToolInvocationState(StrEnum):
    REQUESTED = "requested"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ToolInvocationRecord:
    invocation_id: str
    work_unit_id: str
    tool_id: str
    arguments: dict[str, Any]
    call_id: str | None = None
    state: ToolInvocationState
    replay_policy: ReplayPolicy
    sequence: int
    result_reference: str | None = None
    error: str | None = None
    idempotency_key: str | None = None

    @property
    def requires_recovery_review(self) -> bool:
        return (
            self.state in {
                ToolInvocationState.REQUESTED,
                ToolInvocationState.STARTED,
                ToolInvocationState.UNKNOWN,
            }
            and self.replay_policy.requires_human_review
        )
