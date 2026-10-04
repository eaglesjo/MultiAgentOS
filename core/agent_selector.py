"""Deterministic, evidence-driven Agent selection."""

from __future__ import annotations

from dataclasses import dataclass

from agents.registry import build_registry
from core.contracts.agent import AgentContract
from core.contracts.agent_selection import AgentCandidate, AgentPlan, AgentSelection
from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.work_unit import WorkUnit
from runtime.governance import specialist_route


@dataclass(frozen=True)
class EvidenceEngine:
    """Extract structured routing evidence without making the routing decision."""

    def collect(self, work_unit: WorkUnit) -> tuple[EvidenceRecord, ...]:
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

        return tuple(records)


class DeterministicAgentSelector:
    """Select Agents from evidence and existing governance routing policy."""

    def __init__(
        self,
        *,
        evidence_engine: EvidenceEngine | None = None,
        registry=None,
    ) -> None:
        self.evidence_engine = evidence_engine or EvidenceEngine()
        self.registry = registry or build_registry()

    def select(
        self,
        work_unit: WorkUnit,
        *,
        explicit_agents: tuple[str, ...] | None = None,
        evidence: tuple[EvidenceRecord, ...] | None = None,
    ) -> AgentSelection:
        records = evidence or self.evidence_engine.collect(work_unit)

        if explicit_agents:
            selected_ids = explicit_agents
            mode = "explicit"
            reasons = ("caller supplied an explicit Agent route",)
            policy = ("explicit route preserved; automatic selection bypassed",)
        else:
            selected_ids = specialist_route(work_unit)
            mode = "deterministic"
            reasons = (
                "route selected from WorkUnit type/target and governed taxonomy",
            )
            policy = ("route validated by existing governance policy",)

        candidates = tuple(
            AgentCandidate(
                agent_id=agent_id,
                score=1.0,
                reasons=reasons,
                evidence_ids=tuple(record.id for record in records),
            )
            for agent_id in selected_ids
        )
        plan = AgentPlan(
            work_unit_id=work_unit.id,
            selected_agents=selected_ids,
            route=selected_ids,
            candidates=candidates,
            evidence=records,
            confidence=1.0 if explicit_agents or records else 0.5,
            reasons=reasons,
            policy_decisions=policy,
            selection_mode=mode,
        )
        selection = AgentSelection(plan=plan, selected=candidates)
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
        }
        return selection

    def agents(self, selection: AgentSelection) -> tuple[AgentContract, ...]:
        selection.validate()
        return tuple(self.registry.get(agent_id) for agent_id in selection.plan.route)
