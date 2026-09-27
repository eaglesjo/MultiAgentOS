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
        step_list = list(steps)
        plan = self.planner.plan(work_unit, step_list)
        plan.validate()
        self._validate_agents(plan, agents, executors)

        # The parent WorkUnit remains the durable coordination boundary.
        work_unit.transition(WorkStatus.EXECUTING)
        store = WorkStateStore(project_root / ".multiagentos" / "state")
        store.save(work_unit)

        completed: set[str] = set()
        results: list[OrchestrationResult] = []
        handoffs: list[object] = []

        try:
            for step in plan.steps:
                missing = set(step.depends_on) - completed
                if missing:
                    raise RuntimeError(
                        f"Plan dependency not completed for {step.id}: {sorted(missing)}"
                    )
                agent = agents[step.agent_id or ""]
                child = WorkUnit(
                    id=f"{work_unit.id}:{step.id}",
                    objective=step.objective,
                    inputs={"parent_work_unit_id": work_unit.id},
                    metadata={"stage": step.id, "parent_work_unit_id": work_unit.id},
                )
                result = self.orchestrator.run(
                    child,
                    agent,
                    models,
                    executors[agent.id],
                    preferred_model_ids=(preferred_model_ids or {}).get(agent.id),
                    verifier=(verifiers or {}).get(agent.id),
                    reviewer=(reviewers or {}).get(agent.id),
                )
                results.append(result)
                completed.add(step.id)
                work_unit.artifacts.append(f"workunit:{child.id}")
                work_unit.metadata.setdefault("stage_outputs", {})[step.id] = str(result.output)
                if len(results) > 1:
                    previous = plan.steps[len(results) - 2]
                    previous_agent = agents[previous.agent_id or ""]
                    handoffs.append(
                        self.handoffs.create(
                            work_unit.id,
                            previous_agent,
                            agent,
                            summary=f"Stage {previous.id} completed; handoff to {step.id}.",
                            artifacts=[f"workunit:{child.id}"],
                        )
                    )
                store.save(work_unit)

            work_unit.transition(WorkStatus.VERIFYING)
            work_unit.transition(WorkStatus.HANDOFF)
            work_unit.transition(WorkStatus.COMPLETED)
            store.save(work_unit)
            return MultiAgentResult(
                work_unit, plan, tuple(results), tuple(handoffs), True
            )
        except Exception as exc:
            work_unit.metadata["multi_agent_error"] = str(exc)
            if work_unit.status not in {WorkStatus.FAILED, WorkStatus.COMPLETED}:
                work_unit.transition(WorkStatus.FAILED)
            store.save(work_unit)
            raise

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
