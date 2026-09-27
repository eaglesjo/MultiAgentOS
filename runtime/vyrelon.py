"""High-level VYRELON runtime facade."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from agents.registry import build_registry
from core.contracts.agent import AgentContract
from core.contracts.ide import IDECommand, IDECommandKind, IDEWorkRequest
from core.contracts.ai import AIProvider, ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.contracts.vyrelon_runtime import SessionSpec, SessionState
from core.handoff import ReviewPanel, ReviewPanelResult
from core.planning import BasicPlanner
from core.state import SessionStateStore, WorkStateStore
from core.orchestrator import OrchestrationResult, Orchestrator
from profiles.detector import ProfileDetector
from profiles.resolver import ProfileResolver
from integrations.github.gateway import GitHubGatewayClient
from runtime.github import GitHubRuntime
from runtime.github_probe import probe
from runtime.git import GitRuntime
from runtime.local.filesystem import FilesystemRuntime
from runtime.local.patch import PatchRuntime
from runtime.local.path_security import PathPolicy
from runtime.local.shell import PersistentShellRuntime
from runtime.model.config import DEFAULT_CONFIG_PATH, ProviderConfigLoader
from runtime.model.credentials import EnvironmentCredentialResolver
from runtime.model.factory import ConfiguredAdapterFactory
from runtime.model.providers import AIProviderRegistry
from runtime.model.registry import ModelAdapterRegistry
from runtime.model.runtime_loader import ProviderRuntimeLoader
from runtime.mcp.client import MCPClient
from runtime.mcp.config import MCPConfigLoader
from runtime.mcp.session import MCPSessionRegistry
from runtime.mcp.client import MCPClient
from runtime.mcp.config import MCPConfigLoader
from runtime.policy import ExecutionPolicy
from runtime.validation import ValidationReport, ValidationRuntime, ValidationStep
from runtime.repository import RepositoryRuntime
from runtime.multi_agent import MultiAgentResult, MultiAgentRuntime
from runtime.ide.runtime import IDERuntime
from runtime.ide.bridge import IDEBridge, IDEBridgePolicy, IDEBridgeServer
from runtime.agent.ide import IDECodingExecutor, IDEValidationVerifier
from runtime.tool_calling import ToolRuntime
from runtime.builtin_tools import BuiltinToolBindings
from runtime.repository_tools import GitToolBindings, MCPToolBindings


class VYRELONRuntime:
    """Single entry point for project inspection, local tooling, agent execution, and GitHub access."""

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
        self.credentials = EnvironmentCredentialResolver()
        self.adapter_factory = ConfiguredAdapterFactory()
        self.provider_runtime_loader = ProviderRuntimeLoader(policy=self.policy)
        self.mcp_config = MCPConfigLoader()
        self.mcp_sessions = MCPSessionRegistry()
        self.mcp_config = MCPConfigLoader()
        self.mcp_clients: dict[str, MCPClient] = {}
        self.validation = ValidationRuntime(self.policy)
        self.repository = RepositoryRuntime(self.git, self.github, self.policy)
        self.multi_agent = MultiAgentRuntime(self.orchestrator)
        self.ide = IDERuntime()
        self.tool_runtime = ToolRuntime(self.policy)
        self.ide_bridge_server: IDEBridgeServer | None = None

    def start_ide_bridge(
        self,
        *,
        token: str,
        host: str = "127.0.0.1",
        port: int = 8787,
        allow_remote: bool = False,
    ) -> IDEBridgeServer:
        """Start the local IDE bridge against this VYRELON runtime."""
        if self.ide_bridge_server is not None:
            return self.ide_bridge_server
        bridge = IDEBridge(
            policy=IDEBridgePolicy(token=token, allow_remote=allow_remote),
            runtime=self.ide,
            work_handler=self.submit_ide_work,
        )
        self.ide_bridge_server = IDEBridgeServer(bridge, host=host, port=port)
        self.ide_bridge_server.start()
        return self.ide_bridge_server

    def stop_ide_bridge(self) -> None:
        """Stop the VYRELON IDE bridge when it is running."""
        if self.ide_bridge_server is not None:
            self.ide_bridge_server.stop()
            self.ide_bridge_server = None

    def submit_ide_work(
        self,
        request: IDEWorkRequest,
        *,
        models: list[ModelSpec] | None = None,
        executor: AgentExecutor | None = None,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
    ) -> dict[str, object]:
        """Turn an explicit IDE work request into a persistent Agent/WorkUnit execution."""
        project_root = Path(request.context.project_root).resolve()
        agent = self.agent_profile(project_root, request.agent_id)
        work_unit = WorkUnit(
            id=f"ide-{uuid4().hex}",
            objective=request.objective,
            inputs={
                "ide_context": {
                    "kind": request.context.kind.value,
                    "file_path": request.context.file_path,
                    "selection_start": request.context.selection_start,
                    "selection_end": request.context.selection_end,
                    "language_id": request.context.language_id,
                }
            },
            metadata={
                "source": "ide",
                "ide_kind": request.context.kind.value,
                "agent_id": request.agent_id,
            },
        )
        effective_verifier = verifier
        if request.validation_commands:
            effective_verifier = IDEValidationVerifier(
                project_root=project_root,
                commands=request.validation_commands,
                policy=self.policy,
            )
        if models is not None and executor is not None:
            tool_runtime = ToolRuntime(self.policy)
            BuiltinToolBindings(str(project_root), tool_runtime)
            GitToolBindings(str(project_root), tool_runtime)
            effective_executor = IDECodingExecutor(
                delegate=executor,
                project_root=project_root,
                apply_changes=request.apply_changes,
                policy=self.policy,
                tool_runtime=tool_runtime,
            )
            result = self.run_persistent(
                project_root=project_root,
                work_unit=work_unit,
                agent=agent,
                models=models,
                executor=effective_executor,
                preferred_model_ids=list(request.model_ids) or None,
                verifier=effective_verifier,
                reviewer=reviewer,
            )
        else:
            result = self.run_persistent_registered_model(
                project_root=project_root,
                work_unit=work_unit,
                agent=agent,
                preferred_model_ids=list(request.model_ids) or None,
                verifier=effective_verifier,
                reviewer=reviewer,
            )
        output = result.output
        text = getattr(output, "text", str(output))
        ide_result = self.ide.execute(
            request.context.kind,
            IDECommand(
                kind=IDECommandKind.SHOW_MESSAGE,
                arguments={
                    "text": text,
                    "work_unit_id": work_unit.id,
                    "status": work_unit.status.value,
                },
                context=request.context,
            ),
        )
        return {
            "work_unit": work_unit,
            "orchestration": result,
            "ide_result": ide_result,
        }

    def load_mcp_config(self, project_root: Path):
        """Load external MCP server definitions from the project configuration."""
        return self.mcp_config.load(project_root)

    def connect_mcp(self, project_root: Path, server_id: str):
        """Connect one configured external MCP server and return its client."""
        specs = {spec.id: spec for spec in self.load_mcp_config(project_root)}
        try:
            spec = specs[server_id]
        except KeyError as exc:
            raise LookupError(f"MCP server not configured: {server_id}") from exc
        client = MCPClient(spec, cwd=str(project_root))
        client.connect()
        self.mcp_clients[server_id] = client
        return client

    def disconnect_mcp(self, server_id: str) -> None:
        client = self.mcp_clients.pop(server_id, None)
        if client is not None:
            client.close()

    def load_mcp_config(self, project_root: Path):
        return self.mcp_config.load(project_root)

    def connect_mcp(self, project_root: Path, server_id: str):
        specs={s.id:s for s in self.load_mcp_config(project_root)}
        if server_id not in specs: raise LookupError(f"MCP server not configured: {server_id}")
        client=MCPClient(specs[server_id],cwd=str(project_root))
        client.connect(); self.mcp_sessions.add(client)
        return client

    def disconnect_mcp(self, session_id: str) -> None:
        self.mcp_sessions.close(session_id)

    def local_filesystem(self, project_root: Path) -> FilesystemRuntime:
        return FilesystemRuntime(
            policy=self.policy,
            paths=PathPolicy((str(project_root),)),
        )

    def local_shell(self, project_root: Path) -> PersistentShellRuntime:
        return PersistentShellRuntime(
            cwd=str(project_root),
            policy=self.policy,
            paths=PathPolicy((str(project_root),)),
        )

    def local_patch(self, project_root: Path) -> PatchRuntime:
        return PatchRuntime(
            policy=self.policy,
            paths=PathPolicy((str(project_root),)),
        )

    def run_multi_agent(self, project_root: Path, work_unit: WorkUnit, steps, agents: dict[str, AgentContract], models: list[ModelSpec], executors: dict[str, AgentExecutor], *, preferred_model_ids=None, verifiers=None, reviewers=None) -> MultiAgentResult:
        return self.multi_agent.run(project_root, work_unit, steps, agents, models, executors, preferred_model_ids=preferred_model_ids, verifiers=verifiers, reviewers=reviewers)

    def repository_checkpoint(self, project_root: Path, *, metadata: dict[str, object] | None = None):
        return self.repository.checkpoint(project_root, metadata=metadata)

    def repository_recover(self, project_root: Path, checkpoint):
        return self.repository.recover(project_root, checkpoint)

    def repository_evidence(self, project_root: Path, *, repository: str | None = None, ref: str | None = None, validation: dict[str, object] | None = None):
        return self.repository.evidence(project_root, repository=repository, ref=ref, validation=validation)

    def validate(self, project_root: Path, steps: list[ValidationStep], *, persist_evidence: bool = True) -> ValidationReport:
        """Run project validation through the VYRELON local execution boundary."""
        return self.validation.run(project_root, steps, persist_evidence=persist_evidence)

    def inspect(self, project_root: Path):
        return ProfileDetector().detect(project_root)

    def plan(self, work_unit: WorkUnit, steps):
        return BasicPlanner().plan(work_unit, steps)

    def session_store(self, project_root: Path) -> SessionStateStore:
        return SessionStateStore(Path(project_root).resolve() / ".multiagentos" / "sessions")

    def create_session(
        self,
        project_root: Path,
        *,
        session_id: str | None = None,
        agent_id: str | None = None,
        model_id: str | None = None,
        checkpoint_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> SessionState:
        root = Path(project_root).resolve()
        state = SessionState(
            spec=SessionSpec(
                id=session_id or f"session-{uuid4().hex}",
                project_root=str(root),
                agent_id=agent_id,
                model_id=model_id,
                checkpoint_id=checkpoint_id,
                metadata=dict(metadata or {}),
            )
        )
        self.session_store(root).save(state)
        return state

    def load_session(self, project_root: Path, session_id: str) -> SessionState:
        return self.session_store(project_root).load(session_id)

    def attach_work_unit(self, project_root: Path, session_id: str, work_unit_id: str) -> SessionState:
        store = self.session_store(project_root)
        state = store.load(session_id)
        if work_unit_id not in state.work_unit_ids:
            state.work_unit_ids.append(work_unit_id)
        state.metadata["last_work_unit_id"] = work_unit_id
        store.save(state)
        return state

    def session_checkpoint(self, project_root: Path, session_id: str, *, metadata: dict[str, object] | None = None) -> SessionState:
        root = Path(project_root).resolve()
        state = self.load_session(root, session_id)
        checkpoint = self.repository_checkpoint(root, metadata={"session_id": session_id, **dict(metadata or {})})
        state.spec = SessionSpec(
            id=state.spec.id,
            project_root=state.spec.project_root,
            agent_id=state.spec.agent_id,
            model_id=state.spec.model_id,
            checkpoint_id=checkpoint.id,
            metadata=state.spec.metadata,
        )
        state.metadata["checkpoint_id"] = checkpoint.id
        self.session_store(root).save(state)
        return state

    def session_recover(self, project_root: Path, session_id: str) -> tuple[SessionState, tuple[WorkUnit, ...]]:
        root = Path(project_root).resolve()
        state = self.load_session(root, session_id)
        recoverable = []
        work_store = self.state_store(root)
        for work_id in state.work_unit_ids:
            if work_store.exists(work_id):
                work = work_store.load(work_id)
                if work.status in {WorkStatus.FAILED, WorkStatus.PENDING}:
                    recoverable.append(work)
        state.status = "recoverable" if recoverable else state.status
        self.session_store(root).save(state)
        return state, tuple(recoverable)

    def state_store(self, project_root: Path):
        return WorkStateStore(project_root / ".multiagentos" / "state")

    def agents(self, project_root: Path):
        """Return the legacy AgentRegistry for compatibility."""
        detections = self.inspect(project_root)
        profile_ids = tuple(result.profile_id for result in detections)
        return build_registry(profile_ids)

    def profiles(self, project_root: Path):
        """Resolve one ProjectProfile and its deterministic AgentProfiles."""
        return ProfileResolver().resolve(project_root)

    def agent_profile(self, project_root: Path, agent_id: str):
        """Resolve one project-scoped AgentProfile as an AgentContract."""
        _, agent_profiles = self.profiles(project_root)
        for profile in agent_profiles:
            if profile.id == agent_id:
                return profile.to_contract()
        raise LookupError(f"Agent profile not found: {agent_id}")

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

    def credential_checks(self) -> dict[str, tuple[object, ...]]:
        """Check configured environment-variable credentials without exposing values."""
        result: dict[str, tuple[object, ...]] = {}
        for model in self.configured_models():
            environment_variables: list[str] = []
            configured = model.metadata.get("credential_env", [])
            if isinstance(configured, list):
                environment_variables.extend(
                    item for item in configured if isinstance(item, str) and item
                )
            header_env = model.metadata.get("header_env", {})
            if isinstance(header_env, dict):
                environment_variables.extend(
                    item
                    for item in header_env.values()
                    if isinstance(item, str) and item
                )
            checks = self.credentials.check(list(dict.fromkeys(environment_variables)))
            result[model.id] = checks
        return result

    def register_provider(self, provider: AIProvider) -> None:
        """Register provider/model configuration for later model execution."""
        self.providers.register(provider)

    def register_model_adapter(self, adapter_id: str, adapter) -> None:
        """Register a runtime adapter referenced by model metadata."""
        self.model_adapters.register(adapter_id, adapter)

    def configure_model_adapters(self) -> None:
        """Materialize adapters declared by registered model metadata."""
        for model in self.configured_models():
            adapter_id = str(model.metadata.get("adapter_id", model.provider_id))
            if adapter_id in self.model_adapters.list():
                continue
            metadata = dict(model.metadata)
            adapter_kind = str(metadata.get("adapter_kind", ""))
            if adapter_kind in {"cli", "http"}:
                self.register_model_adapter(
                    adapter_id,
                    self.adapter_factory.build(adapter_id, metadata, self.policy),
                )
                continue
            provider = self.providers.get_provider(model.provider_id)
            provider_kind = provider.kind.lower()
            if provider_kind in {"openai", "openai_responses", "anthropic", "anthropic_messages", "gemini", "gemini_generate_content"}:
                self.provider_runtime_loader.materializer.materialize(
                    (provider,), registry=self.model_adapters
                )

    def configured_models(self, provider_id: str | None = None) -> list[ModelSpec]:
        """Return registered models, optionally scoped to one provider."""
        return list(self.providers.models(provider_id))

    def run_configured_work(
        self,
        project_root: Path,
        *,
        objective: str,
        agent_id: str,
        work_unit_id: str | None = None,
        session_id: str | None = None,
        preferred_model_ids: list[str] | None = None,
        validation_commands: tuple[str, ...] = (),
        apply_changes: bool = False,
        system_prompt: str | None = None,
        adapter_overrides: dict[str, object] | None = None,
        mcp_server_ids: tuple[str, ...] = (),
        fallback_model_ids: tuple[str, ...] = (),
        routing_strategy="pool",
    ) -> OrchestrationResult:
        """Run project-configured work without caller-side provider/model wiring."""
        project_root = Path(project_root).resolve()
        self.load_project_provider_config(project_root)
        models = self.configured_models()
        if not models:
            raise ValueError("No configured models found")
        if adapter_overrides:
            for adapter_id, adapter in adapter_overrides.items():
                if adapter_id in self.model_adapters.list():
                    self.model_adapters.replace(adapter_id, adapter)
                else:
                    self.register_model_adapter(adapter_id, adapter)
        self.configure_model_adapters()

        agent = self.agent_profile(project_root, agent_id)
        if preferred_model_ids:
            for model_id in preferred_model_ids:
                self.providers.get_model(model_id)
        elif agent.model_ids:
            preferred_model_ids = list(agent.model_ids)

        from runtime.agent.model import ModelAgentExecutor

        tool_runtime = ToolRuntime(self.policy)
        BuiltinToolBindings(str(project_root), tool_runtime)
        GitToolBindings(str(project_root), tool_runtime)
        for server_id in mcp_server_ids:
            client = self.mcp_clients.get(server_id) or self.connect_mcp(project_root, server_id)
            MCPToolBindings(tool_runtime, client).register_tools()
        if not apply_changes:
            tool_runtime.unregister("patch.apply")

        executor = ModelAgentExecutor(
            adapters={
                adapter_id: self.model_adapters.get(adapter_id)
                for adapter_id in self.model_adapters.list()
            },
            models=models,
            system_prompt=system_prompt,
            fallback_model_ids=fallback_model_ids,
        )
        effective_executor = IDECodingExecutor(
            delegate=executor,
            project_root=project_root,
            apply_changes=apply_changes,
            policy=self.policy,
            tool_runtime=tool_runtime,
        )
        verifier = None
        if validation_commands:
            verifier = IDEValidationVerifier(
                project_root=project_root,
                commands=validation_commands,
                policy=self.policy,
            )
        store = self.state_store(project_root)
        if work_unit_id and store.exists(work_unit_id):
            work_unit = store.load(work_unit_id)
            work_unit.objective = objective
            work_unit.metadata.update({
                "source": "configured-runtime",
                "agent_id": agent_id,
                "apply_changes": apply_changes,
                "runtime": "configured-model",
                "session_id": session_id,
            })
        else:
            work_unit = WorkUnit(
                id=work_unit_id or f"work-{uuid4().hex}",
                objective=objective,
                metadata={
                    "source": "configured-runtime",
                    "agent_id": agent_id,
                    "apply_changes": apply_changes,
                    "runtime": "configured-model",
                    "session_id": session_id,
                },
            )
        if session_id:
            self.attach_work_unit(project_root, session_id, work_unit.id)
        return self.run_persistent(
            project_root=project_root,
            work_unit=work_unit,
            agent=agent,
            models=models,
            executor=effective_executor,
            preferred_model_ids=preferred_model_ids,
            verifier=verifier,
            routing_strategy=routing_strategy,
        )

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
        self.configure_model_adapters()
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

    def run_persistent_registered_model(
        self,
        project_root: Path,
        work_unit: WorkUnit,
        agent: AgentContract,
        preferred_model_ids: list[str] | None = None,
        system_prompt: str | None = None,
        verifier: ResultVerifier | None = None,
        reviewer: ResultReviewer | None = None,
        routing_strategy="pool",
    ) -> OrchestrationResult:
        """Run a configured model through the persistent WorkUnit lifecycle."""
        self.load_project_provider_config(project_root)
        models = self.configured_models()
        if not models:
            raise ValueError("No configured models found")
        self.configure_model_adapters()
        if preferred_model_ids:
            for model_id in preferred_model_ids:
                self.providers.get_model(model_id)
        from runtime.agent.model import ModelAgentExecutor
        executor = ModelAgentExecutor(
            adapters={
                adapter_id: self.model_adapters.get(adapter_id)
                for adapter_id in self.model_adapters.list()
            },
            models=models,
            system_prompt=system_prompt,
        )
        work_unit.metadata["runtime"] = "configured-model"
        if preferred_model_ids:
            work_unit.metadata["model_id"] = preferred_model_ids[0]
        work_unit.metadata["agent_id"] = agent.id
        return self.run_persistent(
            project_root=project_root,
            work_unit=work_unit,
            agent=agent,
            models=models,
            executor=executor,
            verifier=verifier,
            reviewer=reviewer,
            preferred_model_ids=preferred_model_ids,
            routing_strategy=routing_strategy,
        )

    def resume_work(
        self,
        project_root: Path,
        work_unit_id: str,
        *,
        agent_id: str,
        preferred_model_ids: list[str] | None = None,
        validation_commands: tuple[str, ...] = (),
        apply_changes: bool = False,
        fallback_model_ids: tuple[str, ...] = (),
        adapter_overrides: dict[str, object] | None = None,
    ) -> OrchestrationResult:
        """Resume a persisted failed WorkUnit through the same configured runtime."""
        project_root = Path(project_root).resolve()
        store = self.state_store(project_root)
        if not store.exists(work_unit_id):
            raise LookupError(f"Persisted WorkUnit not found: {work_unit_id}")
        work_unit = store.load(work_unit_id)
        if work_unit.status not in {WorkStatus.FAILED, WorkStatus.PENDING}:
            raise ValueError(
                f"WorkUnit {work_unit_id} is not resumable from {work_unit.status.value}"
            )
        work_unit.metadata["resume_count"] = int(work_unit.metadata.get("resume_count", 0)) + 1
        work_unit.metadata["resumed"] = True
        store.save(work_unit)
        return self.run_configured_work(
            project_root,
            objective=work_unit.objective,
            agent_id=agent_id,
            work_unit_id=work_unit.id,
            preferred_model_ids=preferred_model_ids,
            validation_commands=validation_commands,
            apply_changes=apply_changes,
            fallback_model_ids=fallback_model_ids,
            adapter_overrides=adapter_overrides,
        )

    def recoverable_work(self, project_root: Path) -> tuple[WorkUnit, ...]:
        """Return persisted WorkUnits that can be resumed."""
        store = self.state_store(Path(project_root).resolve())
        result = []
        for work_unit_id in store.list_ids():
            work_unit = store.load(work_unit_id)
            if work_unit.status in {WorkStatus.FAILED, WorkStatus.PENDING}:
                result.append(work_unit)
        return tuple(result)

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
            if hasattr(output, "text"):
                work_unit.metadata["model_response"] = output.text
            if hasattr(output, "model_id"):
                work_unit.metadata["model_id"] = output.model_id
            if hasattr(output, "metadata"):
                output_metadata = getattr(output, "metadata")
                if isinstance(output_metadata, dict):
                    work_unit.metadata["model_response_metadata"] = dict(output_metadata)
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

    def mcp_authorizer(self, project_root: Path):
        """Build the project-scoped MCP tool authorizer."""
        from runtime.mcp.policy import MCPToolAuthorizer, MCPToolProfileLoader
        return MCPToolAuthorizer(MCPToolProfileLoader().load(project_root))

    def mcp_tools(self, project_root: Path, agent: AgentContract | None = None, profile_id: str | None = None):
        """List connected MCP tools, optionally filtered by agent/profile policy."""
        from runtime.mcp.proxy import MCPToolProxy
        return MCPToolProxy(self.mcp_clients, self.mcp_authorizer(project_root)).list_tools(agent, profile_id)

    def call_mcp_tool(self, project_root: Path, request, agent: AgentContract | None = None, profile_id: str | None = None):
        """Invoke an MCP tool after applying the VYRELON agent/profile policy."""
        from runtime.mcp.proxy import MCPToolProxy
        return MCPToolProxy(self.mcp_clients, self.mcp_authorizer(project_root)).call(request, agent, profile_id)
