"""Recovery contracts for durable Agent Execution Runtime state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RecoveryDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class RecoveryDisposition(StrEnum):
    NOT_STARTED = "not_started"
    RESUME = "resume"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class RecoveryPlan:
    """Read-only decision describing whether a WorkUnit may be resumed."""

    work_unit_id: str
    disposition: RecoveryDisposition
    pending_tool_call_ids: tuple[str, ...] = ()
    safe_to_resume: bool = False
    reason: str = ""

    @property
    def requires_human_review(self) -> bool:
        return self.disposition == RecoveryDisposition.REVIEW_REQUIRED


@dataclass(frozen=True)
class RecoveryAuthorization:
    """Durable authorization emitted after a human resolves recovery review."""

    work_unit_id: str
    decision: RecoveryDecision
    notes: str = ""
    session_id: str | None = None
    authorized: bool = False
