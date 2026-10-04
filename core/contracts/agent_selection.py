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

    def validate(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("agent candidate agent_id must not be empty")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("agent candidate score must be between 0 and 1")


@dataclass(frozen=True)
class AgentPlan:
    """Auditable result of Agent selection, before execution begins."""

    work_unit_id: str
    selected_agents: tuple[str, ...]
    route: tuple[str, ...]
    candidates: tuple[AgentCandidate, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    confidence: float = 0.0
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
        if self.selection_mode not in {"deterministic", "llm", "hybrid", "explicit"}:
            raise ValueError("unsupported agent plan selection mode")
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
