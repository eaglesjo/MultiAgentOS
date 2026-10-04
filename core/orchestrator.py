"""Minimal executable AGENT_EXECUTION_RUNTIME orchestration loop."""

from dataclasses import dataclass
from collections.abc import Callable

from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.work_unit import WorkUnit
from core.agent_selector import DeterministicAgentSelector, EvidenceEngine
from core.contracts.agent_selection import AgentSelection
from core.delegation import Delegation
from core.lifecycle import LifecycleCoordinator
from core.routing import RoutingStrategy


@dataclass(frozen=True)
class OrchestrationResult:
    work_unit: WorkUnit
    delegation: Delegation
    output: object


class Orchestrator:
    """Coordinate single-agent and multi-agent execution under AGENT_EXECUTION_RUNTIME authority."""

    def __init__(self, lifecycle: LifecycleCoordinator | None = None) -> None:
        self.lifecycle = lifecycle or LifecycleCoordinator()

    def run(
        self,
        work_unit: WorkUnit,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        preferred_model_ids: list[str] | None = None,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        checkpoint: Callable[[WorkUnit], None] | None = None,
    ) -> OrchestrationResult:
        """Run one WorkUnit through the standard single-agent lifecycle."""
        delegation, output = self.lifecycle.run(
            work_unit,
            agent,
            models,
            executor,
            verifier,
            reviewer,
            preferred_model_ids,
            routing_strategy,
            checkpoint=checkpoint,
        )
        return OrchestrationResult(work_unit, delegation, output)

    def run_workflow(
        self,
        *,
        work_unit: WorkUnit,
        stages: list[AgentContract],
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier | None = None,
        reviewers=None,
        executors_by_agent: dict[str, AgentExecutor] | None = None,
        preferred_model_ids_by_agent: dict[str, list[str]] | None = None,
        verifiers_by_agent: dict[str, ResultVerifier] | None = None,
        reviewers_by_agent: dict[str, ResultReviewer] | None = None,
        reviewer_runner=None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        artifact_store=None,
        checkpoint=None,
        start_stage_index: int = 0,
        resume_action: str | None = None,
        resume_output: object = None,
    ):
        """Run a cooperative multi-agent workflow through the orchestrator.

        MultiAgentWorkflow owns stage/handoff/review semantics; this method is
        the stable orchestration entry point used by higher-level runtimes.
        """
        from core.multi_agent_workflow import MultiAgentWorkflow

        return MultiAgentWorkflow().run(
            work_unit=work_unit,
            stages=stages,
            models=models,
            executor=executor,
            verifier=verifier,
            reviewers=reviewers,
            executors_by_agent=executors_by_agent,
            preferred_model_ids_by_agent=preferred_model_ids_by_agent,
            verifiers_by_agent=verifiers_by_agent,
            reviewers_by_agent=reviewers_by_agent,
            reviewer_runner=reviewer_runner,
            preferred_model_ids=preferred_model_ids,
            routing_strategy=routing_strategy,
            artifact_store=artifact_store,
            checkpoint=checkpoint,
            start_stage_index=start_stage_index,
            resume_action=resume_action,
            resume_output=resume_output,
        )

    def select_agents(
        self,
        work_unit: WorkUnit,
        *,
        explicit_agents: tuple[str, ...] | None = None,
        evidence=None,
        repository_evidence=None,
    ) -> AgentSelection:
        """Build a governed AgentPlan from WorkUnit and repository evidence."""
        selector = DeterministicAgentSelector(evidence_engine=EvidenceEngine())
        return selector.select(
            work_unit,
            explicit_agents=explicit_agents,
            evidence=evidence,
            repository_evidence=repository_evidence,
        )

    def run_auto(
        self,
        *,
        work_unit: WorkUnit,
        models: list[ModelSpec],
        executor: AgentExecutor,
        explicit_agents: tuple[str, ...] | None = None,
        repository_evidence=None,
        verifier: ResultVerifier | None = None,
        reviewers=None,
        executors_by_agent: dict[str, AgentExecutor] | None = None,
        preferred_model_ids_by_agent: dict[str, list[str]] | None = None,
        verifiers_by_agent: dict[str, ResultVerifier] | None = None,
        reviewers_by_agent: dict[str, ResultReviewer] | None = None,
        reviewer_runner=None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        artifact_store=None,
        checkpoint=None,
    ):
        """Select a governed Agent route automatically, then execute it."""
        selection = self.select_agents(
            work_unit,
            explicit_agents=explicit_agents,
            repository_evidence=repository_evidence,
        )
        stages = DeterministicAgentSelector().agents(selection)
        result = self.run_workflow(
            work_unit=work_unit,
            stages=list(stages),
            models=models,
            executor=executor,
            verifier=verifier,
            reviewers=reviewers,
            executors_by_agent=executors_by_agent,
            preferred_model_ids_by_agent=preferred_model_ids_by_agent,
            verifiers_by_agent=verifiers_by_agent,
            reviewers_by_agent=reviewers_by_agent,
            reviewer_runner=reviewer_runner,
            preferred_model_ids=preferred_model_ids,
            routing_strategy=routing_strategy,
            artifact_store=artifact_store,
            checkpoint=checkpoint,
        )
        return selection, result

    def run_debug_retry_workflow(
        self,
        *,
        work_unit: WorkUnit,
        developer: AgentContract,
        tester: AgentContract,
        debugger: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier,
        max_retries: int = 2,
        preferred_model_ids: list[str] | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        artifact_store=None,
    ):
        """Run the bounded Developer -> Tester -> Debugger workflow."""
        from core.multi_agent_workflow import MultiAgentWorkflow

        return MultiAgentWorkflow().run_with_debug_retry(
            work_unit=work_unit,
            developer=developer,
            tester=tester,
            debugger=debugger,
            models=models,
            executor=executor,
            verifier=verifier,
            max_retries=max_retries,
            preferred_model_ids=preferred_model_ids,
            routing_strategy=routing_strategy,
            artifact_store=artifact_store,
        )

    def run_review_rework_workflow(
        self,
        *,
        work_unit: WorkUnit,
        developer: AgentContract,
        tester: AgentContract,
        reviewers,
        models: list[ModelSpec],
        executor: AgentExecutor,
        reviewer_runner,
        verifier: ResultVerifier | None = None,
        max_review_cycles: int = 2,
        preferred_model_ids: list[str] | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        artifact_store=None,
        checkpoint=None,
        start_cycle: int = 0,
        resume_action: str | None = None,
        resume_output: object = None,
    ):
        """Run bounded reviewer feedback and rework through the orchestrator."""
        from core.multi_agent_workflow import MultiAgentWorkflow

        return MultiAgentWorkflow().run_with_review_rework(
            work_unit=work_unit,
            developer=developer,
            tester=tester,
            reviewers=reviewers,
            models=models,
            executor=executor,
            reviewer_runner=reviewer_runner,
            verifier=verifier,
            max_review_cycles=max_review_cycles,
            preferred_model_ids=preferred_model_ids,
            routing_strategy=routing_strategy,
            artifact_store=artifact_store,
            checkpoint=checkpoint,
            start_cycle=start_cycle,
            resume_action=resume_action,
            resume_output=resume_output,
        )
