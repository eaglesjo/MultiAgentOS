""""Deterministic, evidence-driven Agent selection."""

from __future__ import annotations

from dataclasses import dataclass

from agents.registry import build_registry
from core.contracts.agent import AgentContract
from core.contracts.agent_selection import AgentCandidate, AgentPlan, AgentSelection
from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.repository import RepositoryEvidence
from core.contracts.work_unit import WorkUnit
from core.agent_selection_policy import AgentSelectionPolicy, LLMFallbackSelector, LLMSelector
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
        llm_selector: LLMSelector | None = None,
        selection_policy: AgentSelectionPolicy | None = None,
    ) -> None:
        self.evidence_engine = evidence_engine or EvidenceEngine()
        self.registry = registry or build_registry()
        self.llm_selector = llm_selector
        self.selection_policy = selection_policy or AgentSelectionPolicy()

    @staticmethod
    def _score_agent(
        agent: AgentContract,
        work_unit: WorkUnit,
        evidence: tuple[EvidenceRecord, ...],
    ) -> tuple[float, tuple[str, ...]]:
        """Score a governed candidate from explicit taxonomy/evidence matches."""
        taxonomy = agent.taxonomy
        target = (work_unit.target or str(work_unit.metadata.get("platform", ""))).lower()
        technology = str(work_unit.metadata.get("technology", "")).lower()
        statements = " ".join(record.statement.lower() for record in evidence)
        score = 0.40
        reasons: list[str] = ["candidate is permitted by governed route"]

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

        candidates: list[AgentCandidate] = []
        for agent_id in selected_ids:
            agent = self.registry.get(agent_id)
            score, candidate_reasons = self._score_agent(agent, work_unit, records)
            candidates.append(
                AgentCandidate(
                    agent_id=agent_id,
                    score=1.0 if explicit_agents else score,
                    reasons=reasons if explicit_agents else candidate_reasons,
                    evidence_ids=tuple(record.id for record in records),
                )
            )

        confidence = 1.0 if explicit_agents else max(
            (candidate.score for candidate in candidates),
            default=0.5,
        )
        if any(record.kind is EvidenceKind.VERIFIED for record in records):
            confidence = min(1.0, confidence + 0.05)

        plan = AgentPlan(
            work_unit_id=work_unit.id,
            selected_agents=selected_ids,
            route=selected_ids,
            candidates=tuple(candidates),
            evidence=records,
            confidence=confidence,
            reasons=reasons,
            policy_decisions=policy,
            selection_mode=mode,
        )
        if self.llm_selector is not None and not explicit_agents:
            fallback = LLMFallbackSelector(
                self.llm_selector,
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
            selection = AgentSelection(plan=plan, selected=tuple(candidates))
        else:
            selection = AgentSelection(plan=plan, selected=tuple(candidates))

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
        }
        return selection

    def agents(self, selection: AgentSelection) -> tuple[AgentContract, ...]:
        selection.validate()
        return tuple(self.registry.get(agent_id) for agent_id in selection.plan.route)
