"""High-level VYRELON runtime facade."""

from __future__ import annotations

from pathlib import Path

from agents.registry import build_registry
from core.contracts.agent import AgentContract
from core.contracts.ai import AIProvider, ModelSpec
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
from runtime.model.providers import AIProviderRegistry
from runtime.model.registry import ModelAdapterRegistry
from runtime.model.config import DEFAULT_CONFIG_PATH, ProviderConfigLoader
from runtime.model.providers import AIProviderRegistry
from runtime.model.registry import ModelAdapterRegistry
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
        self.providers = AIProviderRegistry()
        self.model_adapters = ModelAdapterRegistry()
        self.provider_config = ProviderConfigLoader()
        self.providers = AIProviderRegistry()
        self.model_adapters = ModelAdapterRegistry()

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

    def load_provider_config(self, path: Path) -> None:
        """Load provider/model definitions from a project JSON configuration."""
        self.provider_config.load(path, self.providers)

    def load_project_provider_config(self, project_root: Path) -> bool:
        """Load the optional project provider configuration if present."""
        path = project_root / DEFAULT_CONFIG_PATH
        if not path.exists():
            return False
        self.load_provider_config(path)
        return True

    def register_provider(self, provider: AIProvider) -> None:
        """Register provider/model configuration for later model execution."""
        self.providers.register(provider)

    def register_model_adapter(self, adapter_id: str, adapter) -> None:
        """Register a runtime adapter referenced by model metadata."""
        self.model_adapters.register(adapter_id, adapter)

    def configured_models(
        self, provider_id: str | None = None
    ) -> list[ModelSpec]:
        """Return registered models, optionally scoped to one provider."""
        return list(self.providers.models(provider_id))

    def run_registered_model(
        self,
        work_unit: WorkUnit,
        agent: AgentContract,
        preferred_model_ids: list[str] | None = None,
        system_prompt: str | None = None,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        routing_strategy="pool",
    ) -> OrchestrationResult:
        """Execute using provider/model and adapter configuration registered in VYRELON."""
        from runtime.agent.model import ModelAgentExecutor

        models = self.configured_models()
        if preferred_model_ids:
            for model_id in preferred_model_ids:
                self.providers.get_model(model_id)

        return self.run(
            work_unit=work_unit,
            agent=agent,
            models=models,
            executor=ModelAgentExecutor(
                adapters={
                    adapter_id: self.model_adapters.get(adapter_id)
                    for adapter_id in self.model_adapters.list()
                },
                models=models,
                system_prompt=system_prompt,
            ),
            preferred_model_ids=preferred_model_ids,
            verifier=verifier,
            reviewer=reviewer,
            routing_strategy=routing_strategy,
        )

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

    def run_model(
        self,
        work_unit: WorkUnit,
        agent: AgentContract,
        models: list[ModelSpec],
        adapters: dict[str, object],
        preferred_model_ids: list[str] | None = None,
        system_prompt: str | None = None,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
    ) -> OrchestrationResult:
        """Execute an agent through a provider-neutral model adapter."""
        from runtime.agent.model import ModelAgentExecutor

        return self.run(
            work_unit=work_unit,
            agent=agent,
            models=models,
            executor=ModelAgentExecutor(
                adapters=adapters,
                models=models,
                system_prompt=system_prompt,
            ),
            preferred_model_ids=preferred_model_ids,
            verifier=verifier,
            reviewer=reviewer,
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

    def review_panel(
        self,
        work_unit_id: str,
        reviewers: list[tuple[AgentContract, object]],
        reviewer_runner,
    ) -> ReviewPanelResult:
        return ReviewPanel().review(work_unit_id, reviewers, reviewer_runner)
