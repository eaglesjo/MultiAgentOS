"""High-level VYRELON runtime facade."""

from __future__ import annotations

from pathlib import Path

from agents.registry import build_registry
from core.chat_agent_bridge import ChatAgentBridge, ChatAgentExecutionResult, ChatAgentRequest, ChatAgentResponse
from core.chat_agent_registry import default_chat_agents
from core.chat_agent_router import ChatAgentAssignment, ChatAgentRouter, ChatAgentRoutingStrategy
from core.chat_session import ChatSession, ChatSessionStore
from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.contracts.human_review import HumanReviewDecision
from core.contracts.resume import WorkflowResumeContext
from core.handoff import ReviewPanel, ReviewPanelResult
from core.planning import BasicPlanner
from core.state import WorkStateStore
from core.orchestrator import OrchestrationResult, Orchestrator
from core.multi_agent_workflow import MultiAgentWorkflow, MultiAgentWorkflowResult
from core.artifacts import ArtifactStore
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

    def load_checkpoint(self, work_unit_id: str, project_root: Path | None = None):
        """Load the durable checkpoint associated with a WorkUnit."""
        root = project_root or Path.cwd()
        return self.state_store(root).load_checkpoint(work_unit_id)

    def artifact_store(self, project_root: Path):
        """Return persistent artifact metadata storage for a project."""
        return ArtifactStore(project_root / ".multiagentos" / "artifacts")

    def agents(self, project_root: Path):
        detections = self.inspect(project_root)
        profile_ids = tuple(result.profile_id for result in detections)
        return build_registry(profile_ids)

    def github_probe(self, repository: str) -> dict:
        return probe(repository)

    def openai_chat_agent(self, model: str | None = None):
        """Create the optional OpenAI Chat Agent adapter."""
        from integrations.openai.chat_agent import OpenAIChatAgentAdapter

        return OpenAIChatAgentAdapter(model=model)

    def chat_agent_registry(self):
        """Return the default provider-neutral Chat Agent registry."""
        return default_chat_agents()

    def chat_agent_router(self) -> ChatAgentRouter:
        """Return the policy-neutral Chat Agent router."""
        return ChatAgentRouter(self.chat_agent_registry())

    def route_chat_agent(
        self,
        *,
        preferred_agent_id: str | None = None,
        fallback_agent_ids: tuple[str, ...] = (),
        required_capabilities: frozenset[str] = frozenset(),
        strategy: ChatAgentRoutingStrategy | str = ChatAgentRoutingStrategy.AUTO,
    ) -> ChatAgentAssignment:
        return self.chat_agent_router().route(
            preferred_agent_id=preferred_agent_id,
            fallback_agent_ids=fallback_agent_ids,
            required_capabilities=required_capabilities,
            strategy=strategy,
        )

    def chat_agent_bridge(self) -> ChatAgentBridge:
        """Return the provider-neutral bridge for conversational AI agents."""
        return ChatAgentBridge(self.chat_agent_registry())

    def chat_session_store(self, project_root: Path) -> ChatSessionStore:
        """Return persistent Chat Agent session storage for a project."""
        return ChatSessionStore(project_root / ".multiagentos" / "sessions")

    def create_chat_session(
        self,
        session_id: str,
        chat_agent_id: str = "chatgpt",
        work_unit_id: str | None = None,
    ) -> ChatSession:
        return ChatSession(
            id=session_id,
            chat_agent_id=chat_agent_id,
            work_unit_id=work_unit_id,
        )

    def chat_request(
        self,
        request: ChatAgentRequest,
        adapter,
        agent_id: str | None = None,
    ) -> tuple[object, object, ChatAgentResponse]:
        """Translate a Chat Agent turn into a VYRELON WorkUnit and Plan."""
        return self.chat_agent_bridge().request(request, adapter, agent_id=agent_id)

    def execute_chat_request(
        self,
        request: ChatAgentRequest,
        adapter,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        *,
        chat_agent_id: str | None = None,
        preferred_model_ids: list[str] | None = None,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        routing_strategy="pool",
        session: ChatSession | None = None,
        project_root: Path | None = None,
    ) -> ChatAgentExecutionResult:
        """Execute a Chat Agent turn through the VYRELON lifecycle."""
        root = project_root or Path.cwd()
        return self.chat_agent_bridge().execute(
            request=request,
            adapter=adapter,
            agent=agent,
            models=models,
            executor=executor,
            chat_agent_id=chat_agent_id,
            preferred_model_ids=preferred_model_ids,
            verifier=verifier,
            reviewer=reviewer,
            routing_strategy=routing_strategy,
            state_store=self.state_store(root),
            session_store=self.chat_session_store(root),
            session=session,
        )

    def resume_chat_request(
        self,
        work_unit_id: str,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        *,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
        project_root: Path | None = None,
    ) -> OrchestrationResult:
        """Resume an interrupted Chat Agent WorkUnit from persisted state."""
        root = project_root or Path.cwd()
        return self.chat_agent_bridge().resume(
            work_unit_id,
            state_store=self.state_store(root),
            agent=agent,
            models=models,
            executor=executor,
            verifier=verifier,
            reviewer=reviewer,
            preferred_model_ids=preferred_model_ids,
            routing_strategy=routing_strategy,
        )

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
        project_root: Path | None = None,
    ) -> OrchestrationResult:
        root = project_root or Path.cwd()
        store = self.state_store(root)
        checkpoint_sequence = 0

        def checkpoint(unit: WorkUnit) -> None:
            nonlocal checkpoint_sequence
            checkpoint_sequence += 1
            store.checkpoint(
                unit,
                workflow="orchestration",
                stage=unit.status.value,
                sequence=checkpoint_sequence,
                next_action=(
                    "resume_execution"
                    if unit.status.value not in {"completed", "failed"}
                    else None
                ),
                agent_ids=(agent.id,),
                model_ids=tuple(model.id for model in models),
                resumable=unit.status.value not in {"completed", "failed"},
            )

        return self.orchestrator.run(
            work_unit=work_unit,
            agent=agent,
            models=models,
            executor=executor,
            preferred_model_ids=preferred_model_ids,
            verifier=verifier,
            reviewer=reviewer,
            routing_strategy=routing_strategy,
            checkpoint=checkpoint,
        )

    def resume_workflow(
        self,
        work_unit_id: str,
        agent: AgentContract,
        models: list[ModelSpec],
        executor: AgentExecutor,
        *,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
        project_root: Path | None = None,
    ) -> OrchestrationResult:
        """Reload a durable checkpoint and resume a generic VYRELON workflow."""
        root = project_root or Path.cwd()
        store = self.state_store(root)
        checkpoint = store.load_checkpoint(work_unit_id)
        if not checkpoint.resumable:
            raise ValueError(f"work unit checkpoint is not resumable: {work_unit_id}")
        if checkpoint.workflow != "orchestration":
            raise ValueError(
                f"checkpoint belongs to workflow {checkpoint.workflow!r}, not orchestration"
            )
        if checkpoint.agent_ids and agent.id not in checkpoint.agent_ids:
            raise ValueError("resume agent does not match checkpoint context")
        available_models = {model.id for model in models}
        if checkpoint.model_ids and not set(checkpoint.model_ids).issubset(available_models):
            raise ValueError("resume models do not match checkpoint context")
        work_unit = store.load(work_unit_id)
        if work_unit.status in {WorkStatus.COMPLETED, WorkStatus.FAILED}:
            raise ValueError(f"work unit is terminal and cannot be resumed: {work_unit_id}")
        return self.run(
            work_unit,
            agent,
            models,
            executor,
            verifier=verifier,
            reviewer=reviewer,
            preferred_model_ids=preferred_model_ids,
            routing_strategy=routing_strategy,
            project_root=root,
        )

    def multi_agent_workflow(self) -> MultiAgentWorkflow:
        """Return the VYRELON-controlled multi-agent handoff workflow."""
        return MultiAgentWorkflow()

    def run_multi_agent_workflow(
        self,
        *,
        work_unit: WorkUnit,
        stages: list[AgentContract],
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier | None = None,
        reviewers=None,
        reviewer_runner=None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
        project_root: Path | None = None,
        start_stage_index: int = 0,
        resume_action: str | None = None,
        resume_output: object = None,
    ) -> MultiAgentWorkflowResult:
        """Run a WorkUnit through multiple agents without transferring authority."""
        root = project_root or Path.cwd()
        return self.multi_agent_workflow().run(
            work_unit=work_unit,
            stages=stages,
            models=models,
            executor=executor,
            verifier=verifier,
            reviewers=reviewers,
            reviewer_runner=reviewer_runner,
            preferred_model_ids=preferred_model_ids,
            routing_strategy=routing_strategy,
            artifact_store=self.artifact_store(root),
            checkpoint=lambda unit, **kwargs: self.state_store(root).checkpoint(
                unit,
                workflow="multi_agent",
                metadata={
                    "next_stage_index": kwargs.get("sequence", 0),
                    "resume_output": unit.metadata.get("checkpoint_output"),
                },
                **kwargs,
            ),
            start_stage_index=start_stage_index,
            resume_action=resume_action,
            resume_output=resume_output,
        )

    def resume_multi_agent_workflow(
        self,
        work_unit_id: str,
        *,
        stages: list[AgentContract],
        models: list[ModelSpec],
        executor: AgentExecutor,
        verifier: ResultVerifier | None = None,
        reviewers=None,
        reviewer_runner=None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
        project_root: Path | None = None,
    ) -> MultiAgentWorkflowResult:
        """Reload a multi-agent checkpoint and continue from its next stage."""
        root = project_root or Path.cwd()
        store = self.state_store(root)
        checkpoint = store.load_checkpoint(work_unit_id)
        if not checkpoint.resumable:
            raise ValueError("multi-agent checkpoint is not resumable")
        if checkpoint.workflow != "multi_agent":
            raise ValueError("checkpoint does not belong to multi-agent workflow")
        available_models = {model.id for model in models}
        if checkpoint.model_ids and not set(checkpoint.model_ids).issubset(available_models):
            raise ValueError("resume models do not match checkpoint context")
        if checkpoint.agent_ids and tuple(agent.id for agent in stages) != checkpoint.agent_ids:
            raise ValueError("resume agents do not match checkpoint context")
        work_unit = store.load(work_unit_id)
        if work_unit.status in {WorkStatus.COMPLETED, WorkStatus.FAILED}:
            raise ValueError("work unit is terminal and cannot be resumed")
        next_stage = int(checkpoint.metadata.get("next_stage_index", 0))
        if checkpoint.next_action == "execute_stage":
            return self.run_multi_agent_workflow(
                work_unit=work_unit,
                stages=stages,
                models=models,
                executor=executor,
                verifier=verifier,
                reviewers=reviewers,
                reviewer_runner=reviewer_runner,
                preferred_model_ids=preferred_model_ids,
                routing_strategy=routing_strategy,
                project_root=root,
                start_stage_index=next_stage,
            )
        if checkpoint.next_action in {"verify", "review"}:
            if next_stage != len(stages):
                raise ValueError("verify/review checkpoint does not follow completed stages")
            return self.run_multi_agent_workflow(
                work_unit=work_unit,
                stages=stages,
                models=models,
                executor=executor,
                verifier=verifier,
                reviewers=reviewers,
                reviewer_runner=reviewer_runner,
                preferred_model_ids=preferred_model_ids,
                routing_strategy=routing_strategy,
                project_root=root,
                start_stage_index=len(stages),
                resume_action=checkpoint.next_action,
                resume_output=checkpoint.metadata.get("resume_output"),
            )
        raise ValueError(f"unsupported multi-agent checkpoint action: {checkpoint.next_action!r}")

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
        project_root: Path | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
    ) -> MultiAgentWorkflowResult:
        root = project_root or Path.cwd()
        return self.multi_agent_workflow().run_with_debug_retry(
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
            artifact_store=self.artifact_store(root),
        )
    def review_panel(
        self,
        work_unit_id: str,
        reviewers: list[tuple[AgentContract, object]],
        reviewer_runner,
    ) -> ReviewPanelResult:
        return ReviewPanel().review(work_unit_id, reviewers, reviewer_runner)

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
        project_root: Path | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
        start_cycle: int = 0,
        resume_action: str | None = None,
        resume_output: object = None,
    ) -> MultiAgentWorkflowResult:
        """Run bounded Review -> Rework -> Review under VYRELON authority."""
        root = project_root or Path.cwd()
        result = self.multi_agent_workflow().run_with_review_rework(
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
            artifact_store=self.artifact_store(root),
            start_cycle=start_cycle,
            resume_action=resume_action,
            resume_output=resume_output,
            checkpoint=lambda unit, **kwargs: self.state_store(root).checkpoint(
                unit,
                workflow="review_rework",
                metadata={
                    "review_cycle": unit.metadata.get("review_cycle", kwargs.get("sequence", 0)),
                    "resume_output": unit.metadata.get("checkpoint_output"),
                },
                **kwargs,
            ),
        )
        self.state_store(root).save(result.work_unit)
        return result

    def resume_review_rework_workflow(
        self,
        work_unit_id: str,
        *,
        developer: AgentContract,
        tester: AgentContract,
        reviewers,
        models: list[ModelSpec],
        executor: AgentExecutor,
        reviewer_runner,
        verifier: ResultVerifier | None = None,
        max_review_cycles: int = 2,
        project_root: Path | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
    ) -> MultiAgentWorkflowResult:
        """Resume a review/rework workflow from verify, review, or rework boundary."""
        root = project_root or Path.cwd()
        store = self.state_store(root)
        checkpoint = store.load_checkpoint(work_unit_id)
        if not checkpoint.resumable:
            raise ValueError("review-rework checkpoint is not resumable")
        if checkpoint.workflow != "review_rework":
            raise ValueError("checkpoint does not belong to review-rework workflow")
        work_unit = store.load(work_unit_id)
        if work_unit.status in {WorkStatus.COMPLETED, WorkStatus.FAILED}:
            raise ValueError("work unit is terminal and cannot be resumed")
        raw_context = work_unit.metadata.get("resume_context")
        if not isinstance(raw_context, dict):
            raise ValueError("work unit has no resumable workflow context")
        context = WorkflowResumeContext.from_metadata(raw_context)
        if context.workflow != "review_rework" or context.work_unit_id != work_unit.id:
            raise ValueError("work unit has incompatible resume context")
        if context.max_review_cycles != max_review_cycles:
            raise ValueError("resume max_review_cycles does not match persisted workflow context")
        if context.developer_id != developer.id or context.tester_id != tester.id:
            raise ValueError("resume agents do not match persisted workflow context")
        reviewer_ids = tuple(agent.id for agent, _ in reviewers)
        if reviewer_ids != context.reviewer_ids:
            raise ValueError("resume reviewers do not match persisted workflow context")
        available_models = {model.id for model in models}
        if context.model_ids and not set(context.model_ids).issubset(available_models):
            raise ValueError("resume models do not match persisted workflow context")
        action = checkpoint.next_action
        if action not in {"verify", "review", "rework"}:
            raise ValueError(f"unsupported review-rework checkpoint action: {action!r}")
        cycle = max(0, int(checkpoint.metadata.get("review_cycle", context.review_cycle)) - 1)
        return self.run_review_rework_workflow(
            work_unit=work_unit,
            developer=developer,
            tester=tester,
            reviewers=reviewers,
            models=models,
            executor=executor,
            reviewer_runner=reviewer_runner,
            verifier=verifier,
            max_review_cycles=max_review_cycles,
            project_root=root,
            preferred_model_ids=preferred_model_ids,
            routing_strategy=routing_strategy,
            start_cycle=cycle,
            resume_action=action if action in {"verify", "review"} else None,
            resume_output=checkpoint.metadata.get("resume_output"),
        )

    def resolve_human_review(
        self,
        *,
        work_unit: WorkUnit,
        decision: HumanReviewDecision | str | None = None,
        approved: bool | None = None,
        notes: str = "",
        project_root: Path | None = None,
    ) -> MultiAgentWorkflowResult:
        """Resolve a persisted human gate and save the resulting WorkUnit."""
        root = project_root or Path.cwd()
        if decision is None:
            if approved is None:
                raise ValueError("decision or approved must be provided")
            decision = (
                HumanReviewDecision.APPROVE_COMPLETION
                if approved
                else HumanReviewDecision.REJECT
            )
        decision = HumanReviewDecision.coerce(decision)
        if decision is HumanReviewDecision.APPROVE_REWORK:
            raise ValueError("APPROVE_REWORK requires resume_human_review_rework()")
        result = self.multi_agent_workflow().resolve_human_review(
            work_unit=work_unit,
            approved=decision is HumanReviewDecision.APPROVE_COMPLETION,
            notes=notes,
        )
        work_unit.metadata["human_review_decision"] = decision.value
        self.state_store(root).checkpoint(
            result.work_unit,
            workflow="review_rework",
            stage=result.work_unit.status.value,
            sequence=int(result.work_unit.metadata.get("review_cycle_count", 0)),
            next_action=None,
            agent_ids=tuple(result.work_unit.metadata.get("execution_agent_ids", ())),
            resumable=False,
            metadata={"human_decision": decision.value},
        )
        return result

    def resolve_persisted_human_review(
        self,
        work_unit_id: str,
        *,
        decision: HumanReviewDecision | str,
        notes: str = "",
        project_root: Path | None = None,
    ) -> MultiAgentWorkflowResult:
        """Load a waiting human gate, resolve it, and persist the decision."""
        root = project_root or Path.cwd()
        work_unit = self.state_store(root).load(work_unit_id)
        if work_unit.status is not WorkStatus.WAITING_HUMAN_APPROVAL:
            raise ValueError("work unit is not waiting for human approval")
        raw_context = work_unit.metadata.get("resume_context")
        if not isinstance(raw_context, dict):
            raise ValueError("work unit has no resumable workflow context")
        context = WorkflowResumeContext.from_metadata(raw_context)
        if context.workflow != "review_rework" or context.work_unit_id != work_unit.id:
            raise ValueError("work unit has incompatible resume context")
        return self.resolve_human_review(
            work_unit=work_unit,
            decision=decision,
            notes=notes,
            project_root=root,
        )

    def resume_human_review_rework(
        self,
        work_unit_id: str,
        *,
        developer: AgentContract,
        tester: AgentContract,
        reviewers,
        models: list[ModelSpec],
        executor: AgentExecutor,
        reviewer_runner,
        verifier: ResultVerifier | None = None,
        max_review_cycles: int = 1,
        project_root: Path | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy="pool",
        notes: str = "",
    ) -> MultiAgentWorkflowResult:
        """Load a human-approved gate and authorize a fresh bounded rework cycle."""
        root = project_root or Path.cwd()
        work_unit = self.state_store(root).load(work_unit_id)
        if work_unit.status is not WorkStatus.WAITING_HUMAN_APPROVAL:
            raise ValueError("work unit is not waiting for human approval")
        raw_context = work_unit.metadata.get("resume_context")
        if not isinstance(raw_context, dict):
            raise ValueError("work unit has no resumable workflow context")
        context = WorkflowResumeContext.from_metadata(raw_context)
        if context.workflow != "review_rework" or context.work_unit_id != work_unit.id:
            raise ValueError("work unit has incompatible resume context")
        if context.developer_id != developer.id or context.tester_id != tester.id:
            raise ValueError("resume agents do not match persisted workflow context")
        reviewer_ids = tuple(agent.id for agent, _ in reviewers)
        if reviewer_ids != context.reviewer_ids:
            raise ValueError("resume reviewers do not match persisted workflow context")
        available_models = {model.id for model in models}
        if context.model_ids and not set(context.model_ids).issubset(available_models):
            raise ValueError("resume models do not match persisted workflow context")
        work_unit.metadata["human_review_required"] = False
        work_unit.metadata["human_review_decision"] = HumanReviewDecision.APPROVE_REWORK.value
        if notes.strip():
            work_unit.metadata["human_review_notes"] = notes
        work_unit.metadata["rework_required"] = True
        work_unit.transition(WorkStatus.EXECUTING)
        self.state_store(root).checkpoint(
            work_unit,
            workflow="review_rework",
            stage=WorkStatus.EXECUTING.value,
            sequence=int(context.review_cycle),
            next_action="review_rework",
            agent_ids=(developer.id, tester.id, *reviewer_ids),
            model_ids=tuple(model.id for model in models),
            resumable=True,
            metadata={"human_decision": HumanReviewDecision.APPROVE_REWORK.value},
        )
        result = self.multi_agent_workflow().run_with_review_rework(
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
            artifact_store=self.artifact_store(root),
            checkpoint=lambda unit, **kwargs: self.state_store(root).checkpoint(
                unit,
                workflow="review_rework",
                metadata={
                    "review_cycle": unit.metadata.get("review_cycle", kwargs.get("sequence", 0)),
                    "resume_output": unit.metadata.get("checkpoint_output"),
                },
                **kwargs,
            ),
        )
        self.state_store(root).save(result.work_unit)
        return result
