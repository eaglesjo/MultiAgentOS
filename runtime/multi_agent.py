"""Multi-agent orchestration runtime built on the existing VYRELON contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.planning import PlanStep, WorkPlan
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.handoff import HandoffManager
from core.orchestrator import OrchestrationResult, Orchestrator
from core.planning import BasicPlanner
from core.state import WorkStateStore


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
    ) -> None:
        self.orchestrator = orchestrator or Orchestrator()
        self.planner = planner or BasicPlanner()
        self.handoffs = handoffs or HandoffManager()

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
    ) -> MultiAgentResult:
        """Adapt the legacy plan-shaped API onto the Orchestrator workflow boundary.

        Planning and dependency validation stay here as an application adapter.
        Execution orchestration is owned by Orchestrator -> MultiAgentWorkflow.
        """
        step_list = list(steps)
        plan = self.planner.plan(work_unit, step_list)
        plan.validate()
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
            completed=work_unit.status is WorkStatus.COMPLETED,
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
