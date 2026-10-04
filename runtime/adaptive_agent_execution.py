"""Runtime adapter for bounded adaptive Agent execution.

This module connects the provider-neutral adaptive loop to the existing
AgentExecutor/delegation boundary and turns durable runtime/tool records into
stage-scoped EvidenceRecord objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.adaptive_agent_execution import StageExecutionOutcome, StageExecutor
from core.contracts.agent import AgentContract
from core.contracts.agent_selection import AgentPlan
from core.contracts.ai import ModelSpec
from core.contracts.evidence import EvidenceKind, EvidenceRecord
from core.contracts.execution import AgentExecutor
from core.contracts.work_unit import WorkUnit
from core.delegation import DelegationEngine
from core.state import RuntimeEventStore
from core.tool_ledger import ToolInvocationStore
from core.contracts.tool_ledger import ToolInvocationState
from core.routing import RoutingStrategy


@dataclass(frozen=True)
class RuntimeExecutionEvidenceCollector:
    """Collect bounded execution evidence from the durable runtime journal."""

    event_store: RuntimeEventStore | None = None
    tool_ledger_store: ToolInvocationStore | None = None

    def collect(
        self,
        work_unit: WorkUnit,
        *,
        agent_id: str,
        before_event_sequence: int = 0,
        before_tool_sequence: int = 0,
    ) -> tuple[EvidenceRecord, ...]:
        records: list[EvidenceRecord] = []
        events = (
            self.event_store.load(work_unit.id)
            if self.event_store is not None
            else ()
        )
        for event in events:
            sequence = int(event.get("sequence") or 0)
            if sequence <= before_event_sequence:
                continue
            kind = str(event.get("kind", ""))
            payload = event.get("payload")
            if kind == "tool_result" and isinstance(payload, dict):
                tool_id = str(payload.get("tool_id", ""))
                ok = payload.get("ok") is True
                statement = (
                    f"tool {tool_id} completed successfully"
                    if ok
                    else f"tool {tool_id} returned an execution error"
                )
                records.append(
                    EvidenceRecord(
                        id=f"runtime-event-{work_unit.id}-{sequence}",
                        work_unit_id=work_unit.id,
                        kind=EvidenceKind.VERIFIED if ok else EvidenceKind.FACT,
                        source="runtime.tool_result",
                        statement=statement,
                        metadata={
                            "agent_id": agent_id,
                            "event_sequence": sequence,
                            "tool_id": tool_id,
                            "ok": ok,
                        },
                    )
                )

        records.extend(
            self._collect_tool_ledger(
                work_unit,
                agent_id=agent_id,
                before_sequence=before_tool_sequence,
            )
        )
        return tuple(records)

    def _collect_tool_ledger(
        self,
        work_unit: WorkUnit,
        *,
        agent_id: str,
        before_sequence: int,
    ) -> tuple[EvidenceRecord, ...]:
        if self.tool_ledger_store is None:
            return ()
        records: list[EvidenceRecord] = []
        for item in self.tool_ledger_store.load(work_unit.id):
            if item.sequence <= before_sequence:
                continue
            if item.state not in {
                ToolInvocationState.COMPLETED,
                ToolInvocationState.FAILED,
            }:
                continue
            ok = item.state is ToolInvocationState.COMPLETED
            records.append(
                EvidenceRecord(
                    id=f"tool-ledger-{work_unit.id}-{item.invocation_id}",
                    work_unit_id=work_unit.id,
                    kind=EvidenceKind.VERIFIED if ok else EvidenceKind.FACT,
                    source="runtime.tool_ledger",
                    statement=(
                        f"tool {item.tool_id} invocation completed"
                        if ok
                        else f"tool {item.tool_id} invocation failed"
                    ),
                    metadata={
                        "agent_id": agent_id,
                        "invocation_id": item.invocation_id,
                        "tool_id": item.tool_id,
                        "sequence": item.sequence,
                        "ok": ok,
                    },
                )
            )
        return tuple(records)


@dataclass
class RuntimeStageExecutor(StageExecutor):
    """Execute selected route stages through the native AgentExecutor boundary."""

    agents: dict[str, AgentContract]
    models: list[ModelSpec]
    executors: dict[str, AgentExecutor]
    delegation: DelegationEngine = DelegationEngine()
    preferred_model_ids_by_agent: dict[str, list[str]] | None = None
    preferred_model_ids: list[str] | None = None
    routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL
    evidence_collector: RuntimeExecutionEvidenceCollector | None = None
    confidence_resolver: Callable[
        [WorkUnit, AgentPlan, int, object, tuple[EvidenceRecord, ...]],
        float,
    ] | None = None

    def execute(
        self,
        *,
        work_unit: WorkUnit,
        plan: AgentPlan,
        stage_indices: tuple[int, ...],
    ) -> tuple[StageExecutionOutcome, ...]:
        outcomes: list[StageExecutionOutcome] = []
        for stage_index in stage_indices:
            if stage_index >= len(plan.route):
                raise ValueError(f"stage index out of range: {stage_index}")
            agent_id = plan.route[stage_index]
            try:
                agent = self.agents[agent_id]
                executor = self.executors[agent_id]
            except KeyError as exc:
                raise LookupError(
                    f"runtime executor is not registered for Agent: {agent_id}"
                ) from exc

            before_events = self._last_event_sequence(work_unit)
            before_tools = self._last_tool_sequence(work_unit)
            try:
                delegation = self.delegation.delegate(
                    work_unit,
                    agent,
                    self.models,
                    (self.preferred_model_ids_by_agent or {}).get(
                        agent_id, self.preferred_model_ids
                    ),
                    self.routing_strategy,
                )
                output = executor.execute(
                    agent=agent,
                    model_id=delegation.assignment.model_id,
                    work_unit=work_unit,
                )
                evidence = (
                    self.evidence_collector.collect(
                        work_unit,
                        agent_id=agent_id,
                        before_event_sequence=before_events,
                        before_tool_sequence=before_tools,
                    )
                    if self.evidence_collector is not None
                    else ()
                )
                confidence = self._confidence(
                    work_unit, plan, stage_index, output, evidence
                )
                outcomes.append(
                    StageExecutionOutcome(
                        stage_index=stage_index,
                        agent_id=agent_id,
                        success=True,
                        confidence=confidence,
                        evidence=evidence,
                        reason=f"execution completed using model {delegation.assignment.model_id}",
                    )
                )
            except Exception as exc:
                evidence = (
                    self.evidence_collector.collect(
                        work_unit,
                        agent_id=agent_id,
                        before_event_sequence=before_events,
                        before_tool_sequence=before_tools,
                    )
                    if self.evidence_collector is not None
                    else ()
                )
                outcomes.append(
                    StageExecutionOutcome(
                        stage_index=stage_index,
                        agent_id=agent_id,
                        success=False,
                        confidence=0.0,
                        evidence=evidence,
                        reason=str(exc),
                    )
                )
                if work_unit.status.value != "failed":
                    from core.contracts.work_unit import WorkStatus

                    if work_unit.status is WorkStatus.EXECUTING:
                        work_unit.transition(WorkStatus.FAILED)
        return tuple(outcomes)

    def _confidence(
        self,
        work_unit: WorkUnit,
        plan: AgentPlan,
        stage_index: int,
        output: object,
        evidence: tuple[EvidenceRecord, ...],
    ) -> float:
        if self.confidence_resolver is not None:
            value = self.confidence_resolver(
                work_unit, plan, stage_index, output, evidence
            )
            return max(0.0, min(1.0, float(value)))

        explicit = work_unit.metadata.get("stage_confidence")
        if isinstance(explicit, (int, float)):
            return max(0.0, min(1.0, float(explicit)))

        verified = sum(1 for item in evidence if item.kind is EvidenceKind.VERIFIED)
        failed = sum(
            1
            for item in evidence
            if item.kind is EvidenceKind.FACT
            and "failed" in item.statement
            or item.kind is EvidenceKind.FACT
            and "error" in item.statement
        )
        if failed:
            return max(0.0, verified / max(1, verified + failed))
        if verified:
            return 1.0
        return 0.85

    def _last_event_sequence(self, work_unit: WorkUnit) -> int:
        if self.evidence_collector is None or self.evidence_collector.event_store is None:
            return 0
        events = self.evidence_collector.event_store.load(work_unit.id)
        return int(events[-1].get("sequence") or 0) if events else 0

    def _last_tool_sequence(self, work_unit: WorkUnit) -> int:
        if self.evidence_collector is None or self.evidence_collector.tool_ledger_store is None:
            return 0
        records = self.evidence_collector.tool_ledger_store.load(work_unit.id)
        return records[-1].sequence if records else 0
