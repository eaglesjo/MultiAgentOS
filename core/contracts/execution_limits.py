"""Provider-neutral execution budget and rate-limit contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LimitDisposition(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class ExecutionBudget:
    """Per-WorkUnit limits; None means unlimited."""

    max_tool_calls: int | None = None
    max_rounds: int | None = None
    max_usage_units: int | None = None

    def __post_init__(self) -> None:
        for name in ("max_tool_calls", "max_rounds", "max_usage_units"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class RateLimit:
    """Deterministic fixed-window rate limit."""

    max_calls: int
    window_seconds: int = 60

    def __post_init__(self) -> None:
        if self.max_calls < 0:
            raise ValueError("max_calls must be non-negative")
        if self.window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")


@dataclass(frozen=True)
class LimitDecision:
    disposition: LimitDisposition
    reason: str
    remaining: int | None = None
