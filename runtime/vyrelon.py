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
from core.contracts.work_unit import WorkUnit
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
        )

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
    ) -> MultiAgentWorkflowResult:
        """Run bounded Review -> Rework -> Review under VYRELON authority."""
        root = project_root or Path.cwd()
        return self.multi_agent_workflow().run_with_review_rework(
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
        )

    def resolve_human_review(
        self,
        *,
        work_unit: WorkUnit,
        approved: bool,
        notes: str = "",
    ) -> MultiAgentWorkflowResult:
        """Apply an explicit human decision to an escalated WorkUnit."""
        return self.multi_agent_workflow().resolve_human_review(
            work_unit=work_unit,
            approved=approved,
            notes=notes,
        )
