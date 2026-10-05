"""Deterministic, evidence-driven Agent selection."""

from __future__ import annotations

from dataclasses import dataclass

from agents.registry import build_registry
from agents.catalog import build_agent_catalog
from core.contracts.agent import AgentContract
from runtime.agent_capability import AgentCapabilityRegistry
from core.contracts.agent_selection import AgentCandidate, AgentPlan, AgentSelection, StageConfidence
from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.repository import RepositoryEvidence
from core.contracts.work_unit import WorkUnit
from core.agent_selection_policy import (
    AgentSelectionPolicy,
    AgentSelectionStrategy,
    CandidatePoolExpansionPolicy,
    SelectionFallback,
)
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
        candidate_pool_policy: CandidatePoolExpansionPolicy | None = None,
    ) -> None:
        self.evidence_engine = evidence_engine or EvidenceEngine()
        self.registry = registry or build_registry()
        self.selection_strategy = selection_strategy
        self.selection_policy = selection_policy or AgentSelectionPolicy()
        self.candidate_pool_policy = candidate_pool_policy or CandidatePoolExpansionPolicy()

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
    def _stage_capability_requirements(
        work_unit: WorkUnit,
        stage_agent_id: str,
    ) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
        raw = work_unit.metadata.get("agent_requirements", {})
        if not isinstance(raw, dict):
            return frozenset(), frozenset(), frozenset()
        requirement = raw.get(stage_agent_id, {})
        if not isinstance(requirement, dict):
            return frozenset(), frozenset(), frozenset()

        def normalize(key: str) -> frozenset[str]:
            value = requirement.get(key, ())
            if isinstance(value, str):
                return frozenset({value})
            if isinstance(value, (list, tuple, set, frozenset)):
                return frozenset(str(item) for item in value if str(item).strip())
            return frozenset()

        return normalize("capabilities"), normalize("tools"), normalize("permissions")

    @classmethod
    def _capability_compatible(
        cls,
        work_unit: WorkUnit,
        stage_agent_id: str,
        candidate: AgentContract,
        capability_registry: AgentCapabilityRegistry,
    ) -> bool:
        capabilities, tools, permissions = cls._stage_capability_requirements(
            work_unit, stage_agent_id
        )
        if not (capabilities or tools or permissions):
            return True
        return capability_registry.match(
            candidate.id,
            capabilities=capabilities,
            tools=tools,
            permissions=permissions,
        ).compatible

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

    def _expand_candidate_registry(
        self,
        work_unit: WorkUnit,
        route: tuple[str, ...],
    ) -> bool:
        """Load a platform profile only when a specialist stage lacks alternatives."""
        profile_id = self.candidate_pool_policy.profile_for(work_unit)
        if profile_id is None:
            return False

        needs_expansion = False
        for expected_id in route:
            expected = self.registry.get(expected_id)
            if expected.kind != "specialist":
                continue
            compatible = sum(
                1
                for candidate in self.registry.list()
                if self._compatible(expected, candidate)
            )
            if compatible < self.candidate_pool_policy.min_candidates:
                needs_expansion = True
                break

        if not needs_expansion:
            return False

        existing_ids = {item.id for item in self.registry.list()}
        added = False
        for candidate in build_agent_catalog((profile_id,)):
            if candidate.id in existing_ids:
                continue
            self.registry.register(candidate)
            existing_ids.add(candidate.id)
            added = True
        return added

    def _candidate_pool(
        self,
        work_unit: WorkUnit,
        evidence: tuple[EvidenceRecord, ...],
        route: tuple[str, ...],
        *,
        allow_expansion: bool = True,
    ) -> tuple[AgentCandidate, ...]:
        """Build a bounded candidate pool, expanding specialist profiles only when needed."""
        if allow_expansion:
            self._expand_candidate_registry(work_unit, route)
        by_id: dict[str, tuple[float, tuple[str, ...], set[int]]] = {}
        capability_registry = AgentCapabilityRegistry(self.registry)

        for stage_index, expected_id in enumerate(route):
            expected = self.registry.get(expected_id)
            expected.validate()
            for candidate in self.registry.list():
                candidate.validate()
                if not self._compatible(expected, candidate):
                    continue
                if not self._capability_compatible(
                    work_unit, expected_id, candidate, capability_registry
                ):
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

        ranked_by_stage: dict[int, list[tuple[str, float]]] = {}
        for stage_index, expected_id in enumerate(route):
            stage_candidates = [
                (agent_id, score)
                for agent_id, (score, _reasons, indices) in by_id.items()
                if stage_index in indices
            ]
            stage_candidates.sort(key=lambda item: (-item[1], item[0]))
            expected_score = next(
                (score for agent_id, score in stage_candidates if agent_id == expected_id),
                None,
            )
            limited = stage_candidates[: self.candidate_pool_policy.top_k]
            if expected_score is not None and expected_id not in {agent_id for agent_id, _ in limited}:
                limited.append((expected_id, expected_score))
            if not limited:
                capabilities, tools, permissions = self._stage_capability_requirements(
                    work_unit, expected_id
                )
                if capabilities or tools or permissions:
                    raise LookupError(
                        f"No Agent satisfies capability requirements for stage {expected_id}"
                    )
            ranked_by_stage[stage_index] = limited

        allowed_by_stage = {
            stage_index: {agent_id for agent_id, _ in candidates}
            for stage_index, candidates in ranked_by_stage.items()
        }
        return tuple(
            AgentCandidate(
                agent_id=agent_id,
                score=score,
                reasons=reasons,
                evidence_ids=tuple(record.id for record in evidence),
                stage_indices=tuple(
                    index
                    for index in sorted(indices)
                    if agent_id in allowed_by_stage[index]
                ),
            )
            for agent_id, (score, reasons, indices) in sorted(by_id.items())
            if any(agent_id in allowed_by_stage[index] for index in indices)
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

        candidates = list(
            self._candidate_pool(
                work_unit,
                records,
                selected_ids,
                allow_expansion=not bool(explicit_agents),
            )
        )
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
                    "selection_source": stage.selection_source,
                    "model_confidence": stage.model_confidence,
                }
                for stage in plan.stage_confidences
            ],
        }
        return selection

    def agents(self, selection: AgentSelection) -> tuple[AgentContract, ...]:
        selection.validate()
        return tuple(self.registry.get(agent_id) for agent_id in selection.plan.route)
