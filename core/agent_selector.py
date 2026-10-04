"""Deterministic, evidence-driven Agent selection."""

from __future__ import annotations

from dataclasses import dataclass

from agents.registry import build_registry
from core.contracts.agent import AgentContract
from core.contracts.agent_selection import AgentCandidate, AgentPlan, AgentSelection, StageConfidence
from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.repository import RepositoryEvidence
from core.contracts.work_unit import WorkUnit
from core.agent_selection_policy import AgentSelectionPolicy, SelectionFallback, AgentSelectionStrategy
from core.repository_evidence import RepositoryEvidenceProvider
from runtime.governance import smallest_sufficient_path, specialist_route


@dataclass(frozen=True)
class EvidenceEngine:
    """Extract structured routing evidence without making the routing decision."""

    repository_provider: RepositoryEvidenceProvider = RepositoryEvidenceProvider()

    def collect(
        self,
        work_unit: WorkUnit,
        *,
        repository_evidence: RepositoryEvidence | None = None,
    ) -> tuple[EvidenceRecord, ...]:
        records: list[EvidenceRecord] = []

        def add(source: str, evidence_type: str, value: str, strength: str = "strong") -> None:
            if not value.strip():
                return
            records.append(
                EvidenceRecord(
                    id=f"selection-{work_unit.id}-{len(records) + 1}",
                    work_unit_id=work_unit.id,
                    kind=EvidenceKind.FACT,
                    source=source,
                    statement=f"{evidence_type}={value}",
                    metadata={
                        "evidence_type": evidence_type,
                        "value": value,
                        "strength": strength,
                    },
                )
            )

        add("work_unit.work_type", "work_type", work_unit.work_type)
        add("work_unit.target", "platform", work_unit.target)
        add("work_unit.environment", "environment", work_unit.environment)
        add("work_unit.objective", "task", work_unit.objective, "medium")

        platform = str(work_unit.metadata.get("platform", ""))
        add("work_unit.metadata.platform", "platform", platform)

        technology = str(work_unit.metadata.get("technology", ""))
        add("work_unit.metadata.technology", "technology", technology)

        records.extend(
            self.repository_provider.collect(
                work_unit,
                repository_evidence,
            )
        )
        return tuple(records)


class DeterministicAgentSelector:
    """Select Agents from evidence and existing governance routing policy."""

    def __init__(
        self,
        *,
        evidence_engine: EvidenceEngine | None = None,
        registry=None,
        selection_strategy: AgentSelectionStrategy | None = None,
        selection_policy: AgentSelectionPolicy | None = None,
    ) -> None:
        self.evidence_engine = evidence_engine or EvidenceEngine()
        self.registry = registry or build_registry()
        self.selection_strategy = selection_strategy
        self.selection_policy = selection_policy or AgentSelectionPolicy()

    @staticmethod
    def _score_agent(
        agent: AgentContract,
        work_unit: WorkUnit,
        evidence: tuple[EvidenceRecord, ...],
    ) -> tuple[float, tuple[str, ...]]:
        """Score a candidate from explicit taxonomy/evidence matches."""
        taxonomy = agent.taxonomy
        target = (work_unit.target or str(work_unit.metadata.get("platform", ""))).lower()
        technology = str(work_unit.metadata.get("technology", "")).lower()
        statements = " ".join(record.statement.lower() for record in evidence)
        score = 0.40
        reasons: list[str] = ["candidate is compatible with the governed stage"]

        if taxonomy.platform and taxonomy.platform.lower() in target + " " + statements:
            score += 0.25
            reasons.append(f"platform evidence matches {taxonomy.platform}")
        if taxonomy.technology and taxonomy.technology.lower() in technology + " " + statements:
            score += 0.20
            reasons.append(f"technology evidence matches {taxonomy.technology}")
        if taxonomy.domain and taxonomy.domain.lower() in work_unit.work_type.lower() + " " + statements:
            score += 0.10
            reasons.append(f"domain evidence matches {taxonomy.domain}")
        if any(record.kind is EvidenceKind.VERIFIED for record in evidence):
            score += 0.05
            reasons.append("verified repository evidence is available")

        return min(score, 1.0), tuple(reasons)

    @staticmethod
    def _compatible(expected: AgentContract, candidate: AgentContract) -> bool:
        """Keep alternatives within the semantic role of the expected stage."""
        if candidate.kind != expected.kind:
            return False
        if candidate.kind == "governance":
            return candidate.id == expected.id
        if candidate.taxonomy.domain != expected.taxonomy.domain:
            return False
        if expected.taxonomy.platform and candidate.taxonomy.platform != expected.taxonomy.platform:
            return False
        if expected.taxonomy.specialization and candidate.taxonomy.specialization != expected.taxonomy.specialization:
            return False
        if not expected.taxonomy.platform and candidate.taxonomy.platform:
            return False
        return True

    def _candidate_pool(
        self,
        work_unit: WorkUnit,
        evidence: tuple[EvidenceRecord, ...],
        route: tuple[str, ...],
    ) -> tuple[AgentCandidate, ...]:
        """Build a policy-shaped candidate pool across every governed route stage."""
        by_id: dict[str, tuple[float, tuple[str, ...], set[int]]] = {}

        for stage_index, expected_id in enumerate(route):
            expected = self.registry.get(expected_id)
            expected.validate()
            for candidate in self.registry.list():
                candidate.validate()
                if not self._compatible(expected, candidate):
                    continue
                score, reasons = self._score_agent(candidate, work_unit, evidence)
                if candidate.id in by_id:
                    old_score, old_reasons, indices = by_id[candidate.id]
                    by_id[candidate.id] = (
                        max(old_score, score),
                        tuple(dict.fromkeys((*old_reasons, *reasons))),
                        indices | {stage_index},
                    )
                else:
                    by_id[candidate.id] = (score, reasons, {stage_index})

        return tuple(
            AgentCandidate(
                agent_id=agent_id,
                score=score,
                reasons=reasons,
                evidence_ids=tuple(record.id for record in evidence),
                stage_indices=tuple(sorted(indices)),
            )
            for agent_id, (score, reasons, indices) in sorted(by_id.items())
        )

    def select(
        self,
        work_unit: WorkUnit,
        *,
        explicit_agents: tuple[str, ...] | None = None,
        evidence: tuple[EvidenceRecord, ...] | None = None,
        repository_evidence: RepositoryEvidence | None = None,
    ) -> AgentSelection:
        records = evidence or self.evidence_engine.collect(
            work_unit,
            repository_evidence=repository_evidence,
        )

        if explicit_agents:
            selected_ids = explicit_agents
            mode = "explicit"
            reasons = ("caller supplied an explicit Agent route",)
            policy = ("explicit route preserved; automatic selection bypassed",)
        else:
            try:
                selected_ids = specialist_route(work_unit)
            except ValueError:
                selected_ids = smallest_sufficient_path(work_unit.work_type)
            mode = "deterministic"
            reasons = (
                "route selected from WorkUnit type/target and governed taxonomy",
            )
            policy = ("route validated by existing governance policy",)

        candidates = list(self._candidate_pool(work_unit, records, selected_ids))
        candidate_map = {candidate.agent_id: candidate for candidate in candidates}
        selected_candidates = tuple(candidate_map[agent_id] for agent_id in selected_ids)

        if explicit_agents:
            selected_candidates = tuple(
                AgentCandidate(
                    agent_id=candidate.agent_id,
                    score=1.0,
                    reasons=reasons,
                    evidence_ids=candidate.evidence_ids,
                    stage_indices=candidate.stage_indices,
                )
                for candidate in selected_candidates
            )

        stage_confidences: list[StageConfidence] = []
        if explicit_agents:
            confidence = 1.0
            for index, candidate in enumerate(selected_candidates):
                stage_confidences.append(
                    StageConfidence(index, candidate.agent_id, 1.0, 1.0, 1.0, 1.0)
                )
        else:
            for index, candidate in enumerate(selected_candidates):
                stage_candidates = [
                    item for item in candidates if index in item.stage_indices
                ]
                scores = sorted((item.score for item in stage_candidates), reverse=True)
                best = scores[0] if scores else candidate.score
                second = scores[1] if len(scores) > 1 else None
                margin = (
                    1.0
                    if second is None
                    else max(0.0, min(1.0, best - second))
                )
                verified = sum(1 for record in records if record.kind is EvidenceKind.VERIFIED)
                coverage = min(1.0, verified / max(1, len(records)))
                stage_confidences.append(
                    StageConfidence(
                        index,
                        candidate.agent_id,
                        candidate.score,
                        best,
                        margin,
                        coverage,
                    )
                )
            confidence = (
                sum(
                    (stage.selected_score * 0.6)
                    + (stage.margin * 0.25)
                    + (stage.evidence_coverage * 0.15)
                    for stage in stage_confidences
                )
                / len(stage_confidences)
                if stage_confidences
                else 0.0
            )


        plan = AgentPlan(
            work_unit_id=work_unit.id,
            selected_agents=selected_ids,
            route=selected_ids,
            candidates=tuple(candidates),
            evidence=records,
            confidence=confidence,
            stage_confidences=tuple(stage_confidences),
            reasons=reasons,
            policy_decisions=policy,
            selection_mode=mode,
        )
        if self.selection_strategy is not None and not explicit_agents:
            fallback = SelectionFallback(
                self.selection_strategy,
                policy=self.selection_policy,
            )
            plan = fallback.select(
                work_unit=work_unit,
                deterministic=plan,
                registry=self.registry,
            )
            candidates = list(plan.candidates)
            selected_ids = plan.selected_agents
            mode = plan.selection_mode
            selected_map = {candidate.agent_id: candidate for candidate in candidates}
            selected_candidates = tuple(selected_map[agent_id] for agent_id in selected_ids)
            selection = AgentSelection(plan=plan, selected=selected_candidates)
        else:
            selection = AgentSelection(plan=plan, selected=selected_candidates)

        selection.validate()

        for agent_id in selected_ids:
            agent = self.registry.get(agent_id)
            agent.validate()

        work_unit.assigned_agents[:] = []
        for agent_id in selected_ids:
            work_unit.assign(agent_id)
        work_unit.metadata["agent_plan"] = {
            "selected_agents": list(plan.selected_agents),
            "route": list(plan.route),
            "confidence": plan.confidence,
            "selection_mode": plan.selection_mode,
            "reasons": list(plan.reasons),
            "policy_decisions": list(plan.policy_decisions),
            "evidence_ids": [record.id for record in plan.evidence],
            "candidate_scores": {
                candidate.agent_id: candidate.score for candidate in plan.candidates
            },
            "stage_confidences": [
                {
                    "stage_index": stage.stage_index,
                    "selected_agent_id": stage.selected_agent_id,
                    "selected_score": stage.selected_score,
                    "best_score": stage.best_score,
                    "margin": stage.margin,
                    "evidence_coverage": stage.evidence_coverage,
                }
                for stage in plan.stage_confidences
            ],
        }
        return selection

    def agents(self, selection: AgentSelection) -> tuple[AgentContract, ...]:
        selection.validate()
        return tuple(self.registry.get(agent_id) for agent_id in selection.plan.route)
