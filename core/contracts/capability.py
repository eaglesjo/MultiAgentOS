"""Model capability contracts for VYRELON routing."""

from dataclasses import dataclass, field
from enum import Enum


class CapabilityConfidence(str, Enum):
    DECLARED = "declared"
    OBSERVED = "observed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModelCapabilityProfile:
    """Normalized capabilities exposed by one model."""

    model_id: str
    provider_id: str
    capabilities: frozenset[str] = frozenset()
    confidence: CapabilityConfidence = CapabilityConfidence.DECLARED
    source: str = "model_spec"
    metadata: dict[str, object] = field(default_factory=dict)

    def supports(self, requirements: frozenset[str]) -> bool:
        return requirements.issubset(self.capabilities)

    def match_score(self, requirements: frozenset[str]) -> float:
        if not requirements:
            return 1.0
        return len(self.capabilities & requirements) / len(requirements)


@dataclass(frozen=True)
class CapabilityMatch:
    model_id: str
    required: frozenset[str]
    matched: frozenset[str]
    missing: frozenset[str]
    score: float
    confidence: CapabilityConfidence

    @property
    def compatible(self) -> bool:
        return not self.missing
