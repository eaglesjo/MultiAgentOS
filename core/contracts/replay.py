"""Durable replay and side-effect policy contracts.

Replay safety is intentionally separate from tool side-effect classification:
a read can still be unsafe to replay in some environments, and a mutating
operation can be safe only when an explicit idempotency guarantee exists.
"""
from dataclasses import dataclass
from enum import StrEnum


class ReplayDisposition(StrEnum):
    SAFE = "safe"
    REVIEW_REQUIRED = "review_required"
    NEVER = "never"


@dataclass(frozen=True)
class ReplayPolicy:
    disposition: ReplayDisposition
    reason: str = ""
    idempotency_key: str | None = None

    @property
    def requires_human_review(self) -> bool:
        return self.disposition == ReplayDisposition.REVIEW_REQUIRED

    @property
    def replayable(self) -> bool:
        return self.disposition == ReplayDisposition.SAFE
