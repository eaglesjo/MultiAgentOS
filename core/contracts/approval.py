"""Explicit, scoped approval contracts for side-effecting execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"


@dataclass(frozen=True)
class ApprovalGrant:
    approval_id: str
    decision: ApprovalDecision
    action: str
    work_unit_id: str | None = None
    session_id: str | None = None
    expires_at: str | None = None
    reason: str = ""

    def is_valid(
        self,
        *,
        action: str,
        work_unit_id: str | None = None,
        session_id: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        if self.decision is not ApprovalDecision.APPROVED:
            return False
        if self.action != action:
            return False
        if self.work_unit_id is not None and self.work_unit_id != work_unit_id:
            return False
        if self.session_id is not None and self.session_id != session_id:
            return False
        if self.expires_at is None:
            return True
        try:
            expiry = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return False
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return (now or datetime.now(timezone.utc)) < expiry


@dataclass(frozen=True)
class ApprovalRequirement:
    action: str
    capability: str | None = None
