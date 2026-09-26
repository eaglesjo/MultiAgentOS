"""High-level VYRELON runtime facade."""

from __future__ import annotations

from pathlib import Path

from agents.registry import build_registry
from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.handoff import ReviewPanel, ReviewPanelResult
from core.planning import BasicPlanner
from core.state import WorkStateStore
from core.orchestrator import OrchestrationResult, Orchestrator
from profiles.detector import ProfileDetector
from integrations.github.gateway import GitHubGatewayClient
from runtime.github import GitHubRuntime
from runtime.github_probe import probe
from runtime.git import GitRuntime
from runtime.policy import ExecutionPolicy


class VYRELONRuntime:
    """Single entry point for project inspection, agent execution, and GitHub access."""

    def __init__(
        self,
        policy: ExecutionPolicy | None = None,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        self.policy = policy or ExecutionPolicy()
        self.orchestrator = orchestrator or Orchestrator()
        self.git = GitRuntime(policy=self.policy)
        self.github = GitHubRuntime(
            gateway=GitHubGatewayClient(),
            policy=self.policy,
        )

    def inspect(self, project_root: Path):
        return ProfileDetector().detect(project_root)

    def plan(self, work_unit: WorkUnit, steps):
        return BasicPlanner().plan(work_unit, steps)

    def state_store(self, project_root: Path):
        return WorkStateStore(project_root / ".multiagentos" / "state")

    def agents(self, project_root: Path):
        detections = self.inspect(project_root)
        profile_ids = tuple(result.profile_id for result in detections)
        return build_registry(profile_ids)

    def github_probe(self, repository: str) -> dict:
        return probe(repository)

    def run_persistent(
        self,
        project_root: Path,
        work_unit: WorkUnit,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
    ) -> OrchestrationResult:
        """Run through the VYRELON lifecycle while persisting every terminal state."""
        work_unit.metadata["cwd"] = str(project_root)
        store = self.state_store(project_root)
        if work_unit.status == WorkStatus.FAILED:
            work_unit.transition(WorkStatus.EXECUTING)
        elif work_unit.status == WorkStatus.PENDING:
            work_unit.transition(WorkStatus.EXECUTING)
        store.save(work_unit)
        try:
            result = self.run(
                work_unit=work_unit,
                agent=agent,
                models=models,
                executor=executor,
                verifier=verifier,
                reviewer=reviewer,
                preferred_model_ids=preferred_model_ids,
                routing_strategy=routing_strategy,
            )
            output = result.output
            work_unit.metadata["output"] = str(output)
            for field in ("returncode", "stdout", "stderr"):
                if hasattr(output, field):
                    work_unit.metadata[field] = getattr(output, field)
            store.save(work_unit)
            return result
        except Exception as exc:
            work_unit.metadata["error"] = str(exc)
            store.save(work_unit)
            raise

    def run(
        self,
        work_unit: WorkUnit,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
    ) -> OrchestrationResult:
        return self.orchestrator.run(
            work_unit=work_unit,
            agent=agent,
            models=models,
            executor=executor,
            preferred_model_ids=preferred_model_ids,
            verifier=verifier,
            reviewer=reviewer,
            routing_strategy=routing_strategy,
        )

    def review_panel(
        self,
        work_unit_id: str,
        reviewers: list[tuple[AgentContract, object]],
        reviewer_runner,
    ) -> ReviewPanelResult:
        return ReviewPanel().review(work_unit_id, reviewers, reviewer_runner)
