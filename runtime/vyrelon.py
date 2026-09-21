"""High-level VYRELON runtime facade."""

from __future__ import annotations

from pathlib import Path

from agents.registry import build_registry
from core.chat_agent_bridge import ChatAgentBridge, ChatAgentRequest, ChatAgentResponse
from core.chat_agent_registry import default_chat_agents
from core.contracts.agent import AgentContract
from core.contracts.ai import ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.work_unit import WorkUnit
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

    def openai_chat_agent(self, model: str | None = None):
        """Create the optional OpenAI Chat Agent adapter."""
        from integrations.openai.chat_agent import OpenAIChatAgentAdapter

        return OpenAIChatAgentAdapter(model=model)

    def chat_agent_bridge(self) -> ChatAgentBridge:
        """Return the provider-neutral bridge for conversational AI agents."""
        return ChatAgentBridge(default_chat_agents())

    def chat_request(
        self,
        request: ChatAgentRequest,
        adapter,
        agent_id: str | None = None,
    ) -> tuple[object, object, ChatAgentResponse]:
        """Translate a Chat Agent turn into a VYRELON WorkUnit and Plan."""
        return self.chat_agent_bridge().request(request, adapter, agent_id=agent_id)

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
