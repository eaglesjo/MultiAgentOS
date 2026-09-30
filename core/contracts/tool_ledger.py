"""Durable tool invocation ledger contracts."""
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .replay import ReplayPolicy
from .idempotency import IdempotencyContract, IdempotencyMode


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
    state: ToolInvocationState
    replay_policy: ReplayPolicy
    sequence: int
    call_id: str | None = None
    result_reference: str | None = None
    error: str | None = None
    idempotency_key: str | None = None

    @property
    @property
    def idempotency_contract(self) -> IdempotencyContract:
        return IdempotencyContract(
            IdempotencyMode.KEYED if self.idempotency_key else IdempotencyMode.NONE,
            self.idempotency_key,
        )

    @property
    def replay_safe(self) -> bool:
        return self.replay_policy.replayable and self.idempotency_contract.replay_safe

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
