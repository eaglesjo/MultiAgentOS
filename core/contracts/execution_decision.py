"""Auditable authorization contract for one Agent x Model execution decision.

The decision is immutable and captures the inputs needed to explain why a
specific Agent was authorized to execute with a specific Model at a stage.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from core.contracts.agent_selection import AgentPlan
from core.contracts.work_unit import WorkUnit
from core.routing import Assignment, RoutingExplanation


@dataclass(frozen=True)
class ExecutionDecision:
    """Final execution authorization for one route stage."""

    work_unit_id: str
    stage_index: int
    agent_id: str
    model_id: str
    attempt: int
    selection_source: str
    selection_confidence: float
    routing: RoutingExplanation
    governance_passed: bool
    governance_findings: tuple[str, ...] = ()
    health_available: bool = True
    quota_available: bool = True
    authorized: bool = False

    @property
    def decision_id(self) -> str:
        payload = json.dumps(self.to_metadata(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def assignment(self) -> Assignment:
        return Assignment(self.agent_id, self.model_id)

    def validate(self) -> None:
        if not self.work_unit_id.strip():
            raise ValueError("execution decision work_unit_id must not be empty")
        if self.stage_index < 0:
            raise ValueError("execution decision stage_index must be non-negative")
        if not self.agent_id.strip():
            raise ValueError("execution decision agent_id must not be empty")
        if not self.model_id.strip():
            raise ValueError("execution decision model_id must not be empty")
        if self.attempt < 1:
            raise ValueError("execution decision attempt must be positive")
        if self.selection_source not in {"deterministic", "model", "hybrid", "explicit"}:
            raise ValueError("unsupported execution decision selection_source")
        if not 0.0 <= self.selection_confidence <= 1.0:
            raise ValueError("execution decision selection_confidence must be between 0 and 1")
        if self.routing.agent_id != self.agent_id:
            raise ValueError("execution decision Agent does not match routing explanation")
        if self.routing.selected_model_id != self.model_id:
            raise ValueError("execution decision Model does not match routing explanation")
        if not self.governance_passed and self.authorized:
            raise ValueError("governance-rejected execution cannot be authorized")
        if self.authorized and (not self.health_available or not self.quota_available):
            raise ValueError("unavailable health/quota cannot be authorized")

    @classmethod
    def authorize(
        cls,
        *,
        work_unit: WorkUnit,
        plan: AgentPlan,
        stage_index: int,
        routing: RoutingExplanation,
        attempt: int,
        governance_passed: bool,
        governance_findings: tuple[str, ...] = (),
    ) -> "ExecutionDecision":
        if stage_index >= len(plan.route):
            raise ValueError(f"stage index out of range: {stage_index}")
        agent_id = plan.route[stage_index]
        if routing.agent_id != agent_id:
            raise ValueError("routing Agent does not match planned stage")
        model_id = routing.selected_model_id
        if model_id is None:
            raise LookupError(f"No model selected for Agent: {agent_id}")

        stage = next(
            (item for item in plan.stage_confidences if item.stage_index == stage_index),
            None,
        )
        confidence = stage.score if stage is not None else plan.confidence
        source = stage.selection_source if stage is not None else plan.selection_mode

        selected = next(
            (item for item in routing.candidates if item.model_id == model_id),
            None,
        )
        if selected is None:
            raise LookupError(f"Selected model is absent from routing explanation: {model_id}")

        decision = cls(
            work_unit_id=work_unit.id,
            stage_index=stage_index,
            agent_id=agent_id,
            model_id=model_id,
            attempt=attempt,
            selection_source=source,
            selection_confidence=confidence,
            routing=routing,
            governance_passed=governance_passed,
            governance_findings=tuple(governance_findings),
            health_available=selected.health_available,
            quota_available=selected.quota_available,
            authorized=governance_passed and selected.compatible
            and selected.health_available and selected.quota_available,
        )
        decision.validate()
        return decision

    def to_metadata(self) -> dict[str, object]:
        """Return a stable JSON-compatible audit representation."""
        return {
            "work_unit_id": self.work_unit_id,
            "stage_index": self.stage_index,
            "agent_id": self.agent_id,
            "model_id": self.model_id,
            "attempt": self.attempt,
            "selection_source": self.selection_source,
            "selection_confidence": self.selection_confidence,
            "governance_passed": self.governance_passed,
            "governance_findings": list(self.governance_findings),
            "health_available": self.health_available,
            "quota_available": self.quota_available,
            "authorized": self.authorized,
            "decision_id": self.decision_id,
            "routing_strategy": self.routing.strategy.value,
            "routing_candidates": [
                {
                    "model_id": candidate.model_id,
                    "provider_id": candidate.provider_id,
                    "selected": candidate.selected,
                    "compatible": candidate.compatible,
                    "health_available": candidate.health_available,
                    "quota_available": candidate.quota_available,
                    "capability_score": candidate.capability_score,
                    "quota_score": candidate.quota_score,
                    "missing_capabilities": sorted(candidate.missing_capabilities),
                    "rejection_reasons": list(candidate.rejection_reasons),
                }
                for candidate in self.routing.candidates
            ],
        }
