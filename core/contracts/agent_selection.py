"""Contracts for evidence-driven automatic Agent selection."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.contracts.evidence import EvidenceRecord


@dataclass(frozen=True)
class AgentCandidate:
    agent_id: str
    score: float
    reasons: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    stage_indices: tuple[int, ...] = ()

    def validate(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("agent candidate agent_id must not be empty")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("agent candidate score must be between 0 and 1")
        if any(index < 0 for index in self.stage_indices):
            raise ValueError("agent candidate stage_indices must be non-negative")


@dataclass(frozen=True)
class StageConfidence:
    """Auditable confidence for one governed route stage."""

    stage_index: int
    selected_agent_id: str
    selected_score: float
    best_score: float
    margin: float
    evidence_coverage: float

    def validate(self) -> None:
        if self.stage_index < 0:
            raise ValueError("stage confidence stage_index must be non-negative")
        if not self.selected_agent_id.strip():
            raise ValueError("stage confidence selected_agent_id must not be empty")
        for name, value in (
            ("selected_score", self.selected_score),
            ("best_score", self.best_score),
            ("margin", self.margin),
            ("evidence_coverage", self.evidence_coverage),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"stage confidence {name} must be between 0 and 1")


@dataclass(frozen=True)
class StageConfidence:
    """Auditable confidence for one governed route stage."""

    stage_index: int
    selected_agent_id: str
    selected_score: float
    best_score: float
    margin: float
    evidence_coverage: float

    def validate(self) -> None:
        if self.stage_index < 0:
            raise ValueError("stage confidence stage_index must be non-negative")
        if not self.selected_agent_id.strip():
            raise ValueError("stage confidence selected_agent_id must not be empty")
        for name, value in (
            ("selected_score", self.selected_score),
            ("best_score", self.best_score),
            ("margin", self.margin),
            ("evidence_coverage", self.evidence_coverage),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"stage confidence {name} must be between 0 and 1")


@dataclass(frozen=True)
class AgentPlan:
    """Auditable result of Agent selection, before execution begins."""

    work_unit_id: str
    selected_agents: tuple[str, ...]
    route: tuple[str, ...]
    candidates: tuple[AgentCandidate, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    confidence: float = 0.0
    stage_confidences: tuple[StageConfidence, ...] = ()
    reasons: tuple[str, ...] = ()
    policy_decisions: tuple[str, ...] = ()
    selection_mode: str = "deterministic"

    def validate(self) -> None:
        if not self.work_unit_id.strip():
            raise ValueError("agent plan work_unit_id must not be empty")
        if not self.selected_agents:
            raise ValueError("agent plan requires at least one selected agent")
        if self.route != self.selected_agents:
            raise ValueError("agent plan route must match selected_agents")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("agent plan confidence must be between 0 and 1")
        if self.selection_mode not in {"deterministic", "model", "hybrid", "explicit"}:
            raise ValueError("unsupported agent plan selection mode")
        for stage in self.stage_confidences:
            stage.validate()
        for stage in self.stage_confidences:
            stage.validate()
        for candidate in self.candidates:
            candidate.validate()
        for record in self.evidence:
            record.validate()


@dataclass(frozen=True)
class AgentSelection:
    """Selector output retaining candidates and evidence for auditability."""

    plan: AgentPlan
    selected: tuple[AgentCandidate, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        self.plan.validate()
        for candidate in self.selected:
            candidate.validate()
        selected_ids = tuple(candidate.agent_id for candidate in self.selected)
        if selected_ids != self.plan.selected_agents:
            raise ValueError("selected candidates do not match AgentPlan")
