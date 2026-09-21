"""Explicit human decisions for escalated VYRELON WorkUnits."""

from enum import Enum


class HumanReviewDecision(str, Enum):
    """Decision applied to a WorkUnit waiting for human approval."""

    APPROVE_COMPLETION = "approve_completion"
    APPROVE_REWORK = "approve_rework"
    REJECT = "reject"

    @classmethod
    def coerce(cls, value: "HumanReviewDecision | str") -> "HumanReviewDecision":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"unsupported human review decision: {value}") from exc
