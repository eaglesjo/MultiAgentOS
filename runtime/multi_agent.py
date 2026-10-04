"""Multi-agent orchestration runtime built on the existing AGENT_EXECUTION_RUNTIME contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.evidence import EvidenceRecord
from core.contracts.planning import PlanStep, WorkPlan
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.handoff import HandoffManager
from core.orchestrator import OrchestrationResult, Orchestrator
from core.planning import BasicPlanner
from core.state import WorkStateStore
from runtime.governance import route_plan_steps, validate_specialist_route
from runtime.governance_runtime import GovernanceRuntime


@dataclass(frozen=True)
class AgentStage:
    step: PlanStep
    agent: AgentContract


@dataclass(frozen=True)
class MultiAgentResult:
    work_unit: WorkUnit
    plan: WorkPlan
    stages: tuple[OrchestrationResult, ...]
    handoffs: tuple[object, ...]
    completed: bool


class MultiAgentRuntime:
    """Execute a dependency-ordered plan with distinct agents per stage."""

    def __init__(
        self,
        orchestrator: Orchestrator | None = None,
        planner: BasicPlanner | None = None,
        handoffs: HandoffManager | None = None,
        governance: GovernanceRuntime | None = None,
    ) -> None:
        self.orchestrator = orchestrator or Orchestrator()
        self.planner = planner or BasicPlanner()
        self.handoffs = handoffs or HandoffManager()
        self.governance = governance or GovernanceRuntime()

    @staticmethod
    def route_steps(
        work_unit: WorkUnit,
        *,
        work_type: str | None = None,
    ) -> tuple[PlanStep, ...]:
        """Return native PlanStep objects for the smallest sufficient route."""
        return route_plan_steps(work_unit, work_type=work_type)

    def run(
        self,
        project_root: Path,
        work_unit: WorkUnit,
        steps: Iterable[PlanStep],
        agents: dict[str, AgentContract],
        models: list[ModelSpec],
        executors: dict[str, AgentExecutor],
        *,
        preferred_model_ids: dict[str, list[str]] | None = None,
        verifiers: dict[str, ResultVerifier] | None = None,
        reviewers: dict[str, ResultReviewer] | None = None,
        evidence: tuple[EvidenceRecord, ...] = (),
    ) -> MultiAgentResult:
        """Execute a governed plan through the existing Orchestrator boundary."""
        self.governance.enforce_hold(work_unit)
        self.governance.validate_work_unit(work_unit)
        step_list = list(steps)
        plan = self.planner.plan(work_unit, step_list)
        self.governance.validate_plan(work_unit, plan)
        self._validate_agents(plan, agents, executors)

        completed: set[str] = set()
        for step in plan.steps:
            missing = set(step.depends_on) - completed
            if missing:
                raise RuntimeError(
                    f"Plan dependency not completed for {step.id}: {sorted(missing)}"
                )
            completed.add(step.id)

        store = WorkStateStore(project_root / ".multiagentos" / "state")
        work_unit.transition(WorkStatus.EXECUTING)
        store.save(work_unit)

        stages = [agents[step.agent_id or ""] for step in plan.steps]
        result = self.orchestrator.run_workflow(
            work_unit=work_unit,
            stages=stages,
            models=models,
            executor=executors[stages[0].id],
            executors_by_agent=executors,
            preferred_model_ids_by_agent=preferred_model_ids,
            verifiers_by_agent=verifiers,
            reviewers_by_agent=reviewers,
        )

        artifacts = tuple(
            artifact
            for artifact in work_unit.metadata.get("artifacts", ())
            if hasattr(artifact, "validate")
        )
        try:
            self.governance.validate_artifacts(work_unit, artifacts)
            self.governance.validate_evidence(
                work_unit,
                evidence,
                require_verified=work_unit.release_impact != "none",
            )
        except ValueError:
            if work_unit.status is WorkStatus.COMPLETED:
                work_unit.transition(WorkStatus.BLOCKED)
            store.save(work_unit)
            raise

        if work_unit.release_impact != "none":
            self.governance.mark_execution_ready_for_approval(
                work_unit,
                evidence=evidence,
            )

        handoffs = tuple(
            stage.handoff for stage in result.stages if stage.handoff is not None
        )
        store.save(work_unit)
        return MultiAgentResult(
            work_unit=work_unit,
            plan=plan,
            stages=tuple(
                OrchestrationResult(
                    work_unit=work_unit,
                    delegation=stage.delegation,
                    output=stage.output,
                )
                for stage in result.stages
            ),
            handoffs=handoffs,
            completed=work_unit.status in {
                WorkStatus.COMPLETED,
                WorkStatus.READY_FOR_APPROVAL,
                WorkStatus.USER_APPROVED,
                WorkStatus.RELEASED,
            },
        )

    @staticmethod
    def _validate_agents(
        plan: WorkPlan,
        agents: dict[str, AgentContract],
        executors: dict[str, AgentExecutor],
    ) -> None:
        for step in plan.steps:
            if not step.agent_id:
                raise ValueError(f"Plan step requires an agent: {step.id}")
            if step.agent_id not in agents:
                raise LookupError(f"Agent not registered for plan step: {step.agent_id}")
            if step.agent_id not in executors:
                raise LookupError(f"Executor not registered for agent: {step.agent_id}")
