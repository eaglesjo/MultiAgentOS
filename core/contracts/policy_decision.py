"""Provider-neutral durable policy decision contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DecisionCategory(StrEnum):
    PERMISSION = "permission"
    CAPABILITY = "capability"
    APPROVAL = "approval"
    BUDGET = "budget"
    RATE_LIMIT = "rate_limit"
    RECOVERY = "recovery"
    MODEL_ROUTING = "model_routing"


class DecisionDisposition(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class PolicyDecision:
    work_unit_id: str
    category: DecisionCategory
    disposition: DecisionDisposition
    reason: str
    action: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] | None = None
