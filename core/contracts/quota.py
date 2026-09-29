"""Provider-neutral quota and rate-limit contracts for AGENT_EXECUTION_RUNTIME."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class QuotaConfidence(StrEnum):
    ACTUAL = "actual"
    OBSERVED = "observed"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class QuotaDimension:
    """One quota/rate-limit dimension such as requests or tokens."""

    name: str
    limit: int | float | None = None
    used: int | float | None = None
    remaining: int | float | None = None
    reset_at: datetime | None = None
    window_seconds: int | None = None
    confidence: QuotaConfidence = QuotaConfidence.UNKNOWN
    source: str = "unknown"

    @property
    def utilization(self) -> float | None:
        if self.limit is None or self.limit <= 0 or self.used is None:
            return None
        return min(1.0, max(0.0, float(self.used) / float(self.limit)))


@dataclass(frozen=True)
class QuotaSnapshot:
    """Latest quota intelligence for one configured model."""

    model_id: str
    provider_id: str
    observed_at: datetime
    dimensions: tuple[QuotaDimension, ...] = ()
    scope: str = "model"
    metadata: dict[str, Any] = field(default_factory=dict)

    def dimension(self, name: str) -> QuotaDimension | None:
        for item in self.dimensions:
            if item.name == name:
                return item
        return None

    @property
    def confidence(self) -> QuotaConfidence:
        if any(item.confidence is QuotaConfidence.ACTUAL for item in self.dimensions):
            return QuotaConfidence.ACTUAL
        if any(item.confidence is QuotaConfidence.ESTIMATED for item in self.dimensions):
            return QuotaConfidence.ESTIMATED
        if any(item.confidence is QuotaConfidence.OBSERVED for item in self.dimensions):
            return QuotaConfidence.OBSERVED
        return QuotaConfidence.UNKNOWN
