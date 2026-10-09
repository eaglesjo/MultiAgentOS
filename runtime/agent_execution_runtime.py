"""High-level Agent Execution Runtime facade."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from agents.registry import build_registry
from core.chat_agent_bridge import ChatAgentBridge, ChatAgentExecutionResult, ChatAgentRequest, ChatAgentResponse
from core.chat_agent_registry import default_chat_agents
from core.chat_agent_router import ChatAgentAssignment, ChatAgentRouter, ChatAgentRoutingStrategy
from core.chat_session import ChatSession, ChatSessionStore
from core.contracts.human_review import HumanReviewDecision
from core.contracts.execution_mission import ExecutionMission, MissionOperation
from core.contracts.resume import WorkflowResumeContext
from core.contracts.recovery import RecoveryAuthorization, RecoveryDecision, RecoveryDisposition, RecoveryPlan
from core.multi_agent_workflow import MultiAgentWorkflow, MultiAgentWorkflowResult
from core.artifacts import ArtifactStore
from runtime.chat_config import load_chat_config
from runtime.chat_adapter_registry import resolve_project_chat_adapter
from core.contracts.agent import AgentContract
from core.contracts.ide import IDECommand, IDECommandKind, IDEWorkRequest
from core.contracts.ai import AIProvider, ModelSpec
from core.contracts.execution import AgentExecutor, ResultReviewer, ResultVerifier
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.contracts.agent_execution_runtime import SessionSpec, SessionState
from core.contracts.execution_limits import ExecutionBudget, RateLimit
from core.contracts.policy_decision import DecisionCategory, DecisionDisposition, PolicyDecision
from core.policy_decision import PolicyDecisionStore
from core.handoff import ReviewPanel, ReviewPanelResult
from core.planning import BasicPlanner
from core.state import RuntimeEventStore, SessionStateStore, WorkStateStore
from core.tool_ledger import ToolInvocationStore
from core.execution_state import ExecutionStateStore
from core.recovery_audit import RecoveryAuditStore
from core.orchestrator import OrchestrationResult, Orchestrator
from core.agent_selection_policy import AgentSelectionPolicy, AgentSelectionStrategy, SelectionFallback
from core.agent_selector import DeterministicAgentSelector, EvidenceEngine
from core.adaptive_agent_execution import AdaptiveAgentExecutionLoop, AdaptiveExecutionPolicy, ExecutionRound
from runtime.adaptive_agent_execution import RuntimeExecutionEvidenceCollector, RuntimeStageExecutor
from core.routing import AIRouter, RoutingStrategy
from profiles.detector import ProfileDetector
from profiles.resolver import ProfileResolver
from integrations.github.gateway import GitHubGatewayClient
from runtime.github import GitHubRuntime
from runtime.discovery import ProviderDiscoveryAdapter
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
from runtime.policy import ExecutionPolicy
from runtime.validation import ValidationReport, ValidationRuntime, ValidationStep
from runtime.repository import RepositoryRuntime
from runtime.multi_agent import MultiAgentResult, MultiAgentRuntime
from runtime.ide.runtime import IDERuntime
from runtime.ide.bridge import IDEBridge, IDEBridgePolicy, IDEBridgeServer
from runtime.agent.ide import IDECodingExecutor, IDEValidationVerifier
from runtime.tool_calling import ToolRuntime
from runtime.harness import ExecutionHarness
from runtime.work_unit_execution import AutomaticExecutionResult, AutomaticWorkUnitExecutor
from runtime.builtin_tools import BuiltinToolBindings
from runtime.repository_tools import GitHubToolBindings, GitToolBindings, MCPToolBindings
from runtime.quota import QuotaIntelligence, QuotaStore, quota_available
from runtime.capability import CapabilityRegistry, CapabilityStore
from runtime.health import ModelHealthRegistry, ModelHealthStore
from runtime.model_control import ModelControlPlane


class AgentExecutionRuntime:
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
        """Start the local IDE bridge against this AGENT_EXECUTION_RUNTIME runtime."""
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
        """Stop the AGENT_EXECUTION_RUNTIME IDE bridge when it is running."""
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
        adapter_overrides: dict[str, object] | None = None,
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
            source_identity = self.workspace_identity(project_root)
            GitHubToolBindings(
                tool_runtime,
                self.github,
                local_available=False,
                source_sha=(
                    str(source_identity["head"])
                    if source_identity is not None and source_identity.get("head")
                    else None
                ),
                source_clean=(
                    source_identity is not None
                    and source_identity.get("dirty") is False
                ),
                source_identity_provider=lambda: self.workspace_identity(project_root),
            )
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
            result = self.run_configured_work(
                project_root,
                objective=request.objective,
                agent_id=request.agent_id,
                preferred_model_ids=list(request.model_ids) or None,
                validation_commands=request.validation_commands,
                apply_changes=request.apply_changes,
                adapter_overrides=adapter_overrides,
            )
        work_unit = result.work_unit
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

    def run_auto(
        self,
        work_unit: WorkUnit,
        models: list[ModelSpec],
        executor: AgentExecutor,
        *,
        explicit_agents: tuple[str, ...] | None = None,
        repository_evidence=None,
        project_root: Path | None = None,
        selection_strategy: AgentSelectionStrategy | None = None,
        selection_policy: AgentSelectionPolicy | None = None,
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
        """Select a governed Agent route automatically, then execute it.

        When a project root is supplied, persist the WorkUnit before execution
        and after either success or failure so automatic Agent workflows have
        the same durable recovery boundary as other runtime entry points.
        """
        root = Path(project_root).resolve() if project_root is not None else None
        store = self.state_store(root) if root is not None else None
        if root is not None:
            work_unit.metadata["cwd"] = str(root)
            if "source_identity" not in work_unit.metadata:
                identity = self.workspace_identity(root)
                if identity is not None:
                    work_unit.metadata["source_identity"] = identity
            store.save(work_unit)
        if repository_evidence is None and root is not None:
            repository_evidence = self.repository.evidence(root)
        try:
            result = self.orchestrator.run_auto(
                work_unit=work_unit,
                models=models,
                executor=executor,
                explicit_agents=explicit_agents,
                repository_evidence=repository_evidence,
                selection_strategy=selection_strategy,
                selection_policy=selection_policy,
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
        except Exception as exc:
            work_unit.metadata["error"] = str(exc)
            if store is not None:
                store.save(work_unit)
            raise
        if store is not None:
            store.save(work_unit)
        return result

    def run_adaptive(
        self,
        project_root: Path,
        work_unit: WorkUnit,
        models: list[ModelSpec],
        executors_by_agent: dict[str, AgentExecutor],
        *,
        explicit_agents: tuple[str, ...] | None = None,
        repository_evidence=None,
        selection_strategy: AgentSelectionStrategy | None = None,
        selection_policy: AgentSelectionPolicy | None = None,
        preferred_model_ids_by_agent: dict[str, list[str]] | None = None,
        preferred_model_ids: list[str] | None = None,
        routing_strategy: RoutingStrategy | str = RoutingStrategy.POOL,
        policy: AdaptiveExecutionPolicy | None = None,
        confidence_resolver=None,
    ) -> tuple[ExecutionRound, ...]:
        """Execute a governed route with bounded specialist-only adaptive reselection."""
        root = Path(project_root).resolve()
        store = self.state_store(root)
        work_unit.metadata["cwd"] = str(root)
        if "source_identity" not in work_unit.metadata:
            identity = self.workspace_identity(root)
            if identity is not None:
                work_unit.metadata["source_identity"] = identity
        try:
            if work_unit.status in {WorkStatus.PENDING, WorkStatus.FAILED}:
                work_unit.transition(WorkStatus.EXECUTING)
            elif work_unit.status is not WorkStatus.EXECUTING:
                raise ValueError(
                    f"adaptive execution cannot start from {work_unit.status.value}"
                )
            store.save(work_unit)
            registry = build_registry()
            initial_selector = DeterministicAgentSelector(
                evidence_engine=EvidenceEngine(),
                selection_strategy=selection_strategy,
                selection_policy=selection_policy,
                registry=registry,
            )
            selection = initial_selector.select(
                work_unit,
                explicit_agents=explicit_agents,
                repository_evidence=(
                    repository_evidence
                    if repository_evidence is not None
                    else self.repository.evidence(root)
                ),
            )
            selector = DeterministicAgentSelector(
                evidence_engine=EvidenceEngine(),
                selection_strategy=None,
                selection_policy=selection_policy,
                registry=registry,
            )
            fallback = (
                SelectionFallback(selection_strategy, policy=selection_policy)
                if selection_strategy is not None
                else None
            )
            collector = RuntimeExecutionEvidenceCollector(
                event_store=self.event_store(root),
                tool_ledger_store=self.tool_ledger_store(root),
            )
            capability_registry = CapabilityRegistry(
                CapabilityStore(root / ".multiagentos" / "capabilities")
            )
            quota_store = QuotaStore(root / ".multiagentos" / "quota")
            quota_snapshots = {
                model.id: quota_store.load(model.id)
                for model in models
                if quota_store.exists(model.id)
            }
            health_store = ModelHealthStore(root / ".multiagentos" / "health")
            health_snapshots = {
                model.id: health_store.load(model.id)
                for model in models
                if health_store.exists(model.id)
            }
            stage_executor = RuntimeStageExecutor(
                agents={agent.id: agent for agent in registry.list()},
                models=models,
                executors=executors_by_agent,
                preferred_model_ids_by_agent=preferred_model_ids_by_agent,
                preferred_model_ids=preferred_model_ids,
                routing_strategy=routing_strategy,
                capability_registry=capability_registry,
                quota_snapshots=quota_snapshots,
                health_snapshots=health_snapshots,
                evidence_collector=collector,
                confidence_resolver=confidence_resolver,
            )
            loop = AdaptiveAgentExecutionLoop(
                selector=selector,
                registry=registry,
                executor=stage_executor,
                selection_fallback=fallback,
                policy=policy,
            )
            rounds = loop.run(work_unit=work_unit, initial_plan=selection.plan)
            if rounds and rounds[-1].success:
                if work_unit.status is WorkStatus.EXECUTING:
                    work_unit.transition(WorkStatus.VERIFYING)
                if work_unit.status is WorkStatus.VERIFYING:
                    work_unit.transition(WorkStatus.COMPLETED)
            elif work_unit.status in {WorkStatus.EXECUTING, WorkStatus.VERIFYING}:
                work_unit.transition(WorkStatus.FAILED)
            store.save(work_unit)
            return rounds
        except Exception as exc:
            work_unit.metadata["error"] = str(exc)
            if work_unit.status in {WorkStatus.PENDING, WorkStatus.PLANNING, WorkStatus.EXECUTING, WorkStatus.VERIFYING}:
                work_unit.transition(WorkStatus.FAILED)
            store.save(work_unit)
            raise
    

    def reselect_agents(
        self,
        work_unit: WorkUnit,
        *,
        evidence,
        selection_strategy: AgentSelectionStrategy | None = None,
        selection_policy: AgentSelectionPolicy | None = None,
    ):
        """Re-evaluate Agent routing from evidence produced after execution."""
        return self.orchestrator.reselect_agents(
            work_unit,
            evidence=evidence,
            selection_strategy=selection_strategy,
            selection_policy=selection_policy,
        )

    def repository_checkpoint(self, project_root: Path, *, metadata: dict[str, object] | None = None):
        return self.repository.checkpoint(project_root, metadata=metadata)

    def repository_recover(self, project_root: Path, checkpoint):
        return self.repository.recover(project_root, checkpoint)

    def repository_evidence(self, project_root: Path, *, repository: str | None = None, ref: str | None = None, validation: dict[str, object] | None = None):
        return self.repository.evidence(project_root, repository=repository, ref=ref, validation=validation)

    def validate(self, project_root: Path, steps: list[ValidationStep], *, persist_evidence: bool = True) -> ValidationReport:
        """Run project validation through the AGENT_EXECUTION_RUNTIME local execution boundary."""
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

    def event_store(self, project_root: Path):
        return RuntimeEventStore(Path(project_root) / ".multiagentos" / "events")

    def tool_ledger_store(self, project_root: Path):
        return ToolInvocationStore(Path(project_root) / ".multiagentos" / "tool-ledger")

    def execution_state_store(self, project_root: Path):
        return ExecutionStateStore(Path(project_root) / ".multiagentos" / "execution-state")

    def recovery_audit_store(self, project_root: Path):
        return RecoveryAuditStore(Path(project_root) / ".multiagentos" / "recovery")

    def workspace_identity(self, project_root: Path) -> dict[str, object] | None:
        return self.git.identity(str(Path(project_root).resolve()))

    def load_execution_cursor(self, project_root: Path, work_unit_id: str):
        return self.execution_state_store(project_root).load_cursor(work_unit_id)

    def load_execution_messages(self, project_root: Path, work_unit_id: str):
        return self.execution_state_store(project_root).load_messages(work_unit_id)

    def load_runtime_events(self, project_root: Path, work_unit_id: str) -> tuple[dict[str, object], ...]:
        """Load the durable runtime journal for a WorkUnit."""
        return self.event_store(project_root).load(work_unit_id)

    def inspect_work_unit(self, project_root: Path, work_unit_id: str) -> dict[str, object]:
        """Return a deterministic execution snapshot derived from WorkUnit state and events."""
        work_unit = self.state_store(project_root).load(work_unit_id)
        events = self.event_store(project_root).load(work_unit_id)
        ledger = self.tool_ledger_store(project_root).load(work_unit_id)
        pending_calls: list[str] = []
        completed_calls: set[str] = set()
        last_kind = events[-1]["kind"] if events else None
        for event in events:
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            call_id = payload.get("call_id")
            if not isinstance(call_id, str):
                continue
            if event.get("kind") == "tool_call":
                pending_calls.append(call_id)
            elif event.get("kind") == "tool_result":
                completed_calls.add(call_id)
        pending_calls = [call_id for call_id in pending_calls if call_id not in completed_calls]
        unresolved_ledger = self.tool_ledger_store(project_root).unresolved(work_unit_id)
        if unresolved_ledger:
            pending_calls = [record.invocation_id for record in unresolved_ledger]
        if last_kind == "completed" and work_unit.status is WorkStatus.COMPLETED:
            execution_state = "completed"
        elif pending_calls:
            execution_state = "tool_in_flight"
        elif work_unit.status.value == "failed":
            execution_state = "failed"
        elif events:
            execution_state = "executing"
        else:
            execution_state = "not_started"
        return {
            "work_unit_id": work_unit_id,
            "work_status": work_unit.status.value,
            "execution_state": execution_state,
            "event_count": len(events),
            "last_sequence": events[-1].get("sequence") if events else None,
            "last_event_kind": last_kind,
            "pending_tool_call_ids": tuple(pending_calls),
            "tool_invocation_count": len(ledger),
            "unresolved_tool_invocations": tuple(record.invocation_id for record in unresolved_ledger),
        }

    def recovery_plan(self, project_root: Path, work_unit_id: str) -> RecoveryPlan:
        """Derive a conservative recovery decision without replaying any tool."""
        work_unit = self.state_store(project_root).load(work_unit_id)
        expected_identity = work_unit.metadata.get("source_identity")
        current_identity = self.workspace_identity(project_root)
        if isinstance(expected_identity, dict) and (current_identity is None or dict(expected_identity) != current_identity):
            return RecoveryPlan(
                work_unit_id,
                RecoveryDisposition.REVIEW_REQUIRED,
                reason="workspace source identity changed since the durable execution began",
            )
        snapshot = self.inspect_work_unit(project_root, work_unit_id)
        state = snapshot["execution_state"]
        pending = tuple(snapshot["pending_tool_call_ids"])
        if state == "completed":
            return RecoveryPlan(work_unit_id, RecoveryDisposition.COMPLETED, reason="execution already completed")
        if state == "not_started":
            return RecoveryPlan(work_unit_id, RecoveryDisposition.NOT_STARTED, safe_to_resume=True, reason="no durable execution evidence exists")
        if pending:
            unresolved = self.tool_ledger_store(project_root).unresolved(work_unit_id)
            review_required = tuple(
                record.invocation_id
                for record in unresolved
                if record.requires_recovery_review
            )
            if unresolved and not review_required:
                return RecoveryPlan(
                    work_unit_id,
                    RecoveryDisposition.RESUME,
                    pending_tool_call_ids=tuple(record.invocation_id for record in unresolved),
                    safe_to_resume=True,
                    reason="unresolved tool invocations are explicitly replay-safe",
                )
            return RecoveryPlan(
                work_unit_id,
                RecoveryDisposition.REVIEW_REQUIRED,
                pending_tool_call_ids=review_required or pending,
                reason="a tool invocation has no durable result and replay requires human review",
            )

        return RecoveryPlan(
            work_unit_id,
            RecoveryDisposition.RESUME,
            safe_to_resume=True,
            reason="durable execution ended between tool rounds",
        )
    
    def resolve_recovery_review(
        self,
        project_root: Path,
        work_unit_id: str,
        *,
        decision: RecoveryDecision | str,
        notes: str = "",
        session_id: str | None = None,
    ) -> RecoveryAuthorization:
        """Durably resolve a recovery review without executing the pending tool."""
        root = Path(project_root).resolve()
        plan = self.recovery_plan(root, work_unit_id)
        decision = RecoveryDecision(decision)
        if plan.disposition is not RecoveryDisposition.REVIEW_REQUIRED:
            raise ValueError(
                f"recovery review is not pending: {plan.disposition.value}"
            )
        reason = notes.strip()
        if decision is RecoveryDecision.REJECT:
            work_unit = self.state_store(root).load(work_unit_id)
            if work_unit.status not in {WorkStatus.FAILED, WorkStatus.COMPLETED}:
                work_unit.transition(WorkStatus.FAILED)
                work_unit.metadata["recovery_decision"] = decision.value
                if reason:
                    work_unit.metadata["recovery_notes"] = reason
                self.state_store(root).save(work_unit)
            disposition = DecisionDisposition.DENY
            authorized = False
        else:
            disposition = DecisionDisposition.ALLOW
            authorized = True
        self.policy_decision_store(root).append(
            PolicyDecision(
                work_unit_id=work_unit_id,
                category=DecisionCategory.RECOVERY,
                disposition=disposition,
                reason=reason or (
                    "Human approved recovery replay"
                    if decision is RecoveryDecision.APPROVE
                    else "Human rejected recovery replay"
                ),
                action="runtime.recover",
                session_id=session_id,
                metadata={
                    "source": "agent-execution-runtime",
                    "human_decision": decision.value,
                    "pending_tool_call_ids": list(plan.pending_tool_call_ids),
                },
            )
        )
        return RecoveryAuthorization(
            work_unit_id=work_unit_id,
            decision=decision,
            notes=reason,
            session_id=session_id,
            authorized=authorized,
        )

    def policy_decision_store(self, project_root: Path) -> PolicyDecisionStore:
        return PolicyDecisionStore(Path(project_root).resolve() / ".multiagentos" / "decisions")

    def quota_store(self, project_root: Path):
        """Return the project-scoped persistent model quota store."""
        return QuotaStore(Path(project_root) / ".multiagentos" / "quota")

    def health_registry(self, project_root: Path):
        """Return the project-scoped persistent model health registry."""
        return ModelHealthRegistry(ModelHealthStore(Path(project_root) / ".multiagentos" / "health"))

    def capability_registry(self, project_root: Path):
        """Return the project-scoped persistent model capability registry."""
        return CapabilityRegistry(CapabilityStore(Path(project_root) / ".multiagentos" / "capabilities"))

    def model_control_plane(self, project_root: Path) -> ModelControlPlane:
        """Return the project-scoped unified model control plane."""
        return ModelControlPlane(Path(project_root).resolve())

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

    def explain_model_routing(
        self,
        project_root: Path,
        *,
        agent_id: str,
        preferred_model_ids: list[str] | None = None,
        routing_strategy: str = "pool",
    ):
        """Return provider-neutral routing evidence for a project agent."""
        root = Path(project_root).resolve()
        self.load_project_provider_config(root)
        models = self.configured_models()
        agent = self.agent_profile(root, agent_id)
        preferred = preferred_model_ids
        if preferred is None and agent.model_ids:
            preferred = list(agent.model_ids)
        quota_store = self.quota_store(root)
        health_registry = self.health_registry(root)
        capability_registry = self.capability_registry(root)
        quota_snapshots = {
            model.id: quota_store.load(model.id)
            for model in models
            if quota_store.exists(model.id)
        }
        health_snapshots = {
            model.id: health
            for model in models
            if (health := health_registry.get(model.id)) is not None
        }
        return AIRouter().explain(
            agent.to_contract() if hasattr(agent, "to_contract") else agent,
            models,
            preferred_model_ids=preferred,
            strategy=RoutingStrategy(routing_strategy),
            quota_snapshots=quota_snapshots,
            health_snapshots=health_snapshots,
            capability_registry=capability_registry,
        )

    def discover_models(self, project_root: Path, *, refresh: bool = True):
        """Discover and persist provider capabilities and quota metadata."""
        root = Path(project_root).resolve()
        self.load_project_provider_config(root)
        capability_registry = self.capability_registry(root)
        quota_store = self.quota_store(root)
        adapter = ProviderDiscoveryAdapter(policy=self.policy)
        results = []
        for provider in self.providers.providers():
            if not refresh:
                results.append({"provider": provider.id, "status": "skipped"})
                continue
            result, error = adapter.discover_safe(
                provider,
                models=tuple(provider.models),
            )
            if error is not None:
                results.append({
                    "provider": provider.id,
                    "status": "error",
                    "message": error.message,
                    "retryable": error.retryable,
                })
                continue
            for profile in result.capabilities:
                capability_registry.merge(profile)
            for snapshot in result.quotas:
                quota_store.merge(snapshot)
            results.append({
                "provider": provider.id,
                "status": "ok",
                "capabilities": len(result.capabilities),
                "quotas": len(result.quotas),
                "source": result.source,
            })
        return tuple(results)

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
        execution_budget: ExecutionBudget | None = None,
        rate_limit: RateLimit | None = None,
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
        control_plane = self.model_control_plane(project_root)
        if preferred_model_ids:
            for model_id in preferred_model_ids:
                self.providers.get_model(model_id)
        elif agent.model_ids:
            preferred_model_ids = list(agent.model_ids)
        else:
            # Project-aware automatic routing also considers the latest persisted quota.
            router = AIRouter()
            quota_snapshots = {}
            health_snapshots = {}
            for model in models:
                state = control_plane.state(model)
                if state.quota is not None:
                    quota_snapshots[model.id] = state.quota
                if state.health is not None:
                    health_snapshots[model.id] = state.health
            assignment = router.assign(
                agent,
                models,
                strategy=RoutingStrategy(routing_strategy),
                quota_snapshots=quota_snapshots,
                health_snapshots=health_snapshots,
                capability_registry=control_plane.capability_registry,
            )
            preferred_model_ids = [assignment.model_id]
            fallback_model_ids = tuple(
                model.id
                for model in models
                if model.id != assignment.model_id
                and router.compatible(agent, model)
                and control_plane.state(model).available
            )

        from runtime.agent.model import ModelAgentExecutor
        quota_intelligence = QuotaIntelligence(control_plane.quota_store)
        capability_registry = self.capability_registry(project_root)
        health_registry = control_plane.health_registry

        harness = ExecutionHarness.create(
            project_root,
            policy=self.policy,
            apply_changes=apply_changes,
        )
        for server_id in mcp_server_ids:
            client = self.mcp_clients.get(server_id) or self.connect_mcp(project_root, server_id)
            harness.register_mcp_client(client)

        tool_runtime = harness.tool_runtime
        event_store = harness.event_store
        ledger_store = harness.ledger_store
        execution_state_store = harness.execution_state_store
        persist_runtime_event = harness.event_sink()
        execution_budget = execution_budget or ExecutionBudget()

        executor = ModelAgentExecutor(
            adapters={
                adapter_id: self.model_adapters.get(adapter_id)
                for adapter_id in self.model_adapters.list()
            },
            models=models,
            system_prompt=system_prompt,
            fallback_model_ids=fallback_model_ids,
            quota_intelligence=quota_intelligence,
            health_registry=health_registry,
            model_control=control_plane,
            capability_registry=capability_registry,
            event_sink=persist_runtime_event,
            ledger_store=ledger_store,
            cursor_store=execution_state_store,
            limit_store=harness.execution_limit_store,
            execution_budget=execution_budget,
            rate_limit=rate_limit,
            decision_store=harness.decision_store,
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
        harness.decision_store.append(PolicyDecision(
            work_unit_id=work_unit.id,
            category=DecisionCategory.MODEL_ROUTING,
            disposition=DecisionDisposition.ALLOW,
            reason="model routing selected the configured execution model",
            action="model.route",
            session_id=session_id,
            metadata={
                "strategy": str(routing_strategy),
                "model_id": preferred_model_ids[0] if preferred_model_ids else None,
                "fallback_count": len(fallback_model_ids),
            },
        ))
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
        """Execute using provider/model and adapter configuration registered in AGENT_EXECUTION_RUNTIME."""
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
        """Resume a persisted WorkUnit only when its durable recovery plan permits replay."""
        project_root = Path(project_root).resolve()
        store = self.state_store(project_root)
        if not store.exists(work_unit_id):
            raise LookupError(f"Persisted WorkUnit not found: {work_unit_id}")
        work_unit = store.load(work_unit_id)
        plan = self.recovery_plan(project_root, work_unit_id)
        self.recovery_audit_store(project_root).append(
            plan,
            source_identity=self.workspace_identity(project_root),
        )
        PolicyDecisionStore(Path(project_root) / ".multiagentos" / "decisions").append(PolicyDecision(
            work_unit_id=work_unit_id,
            category=DecisionCategory.RECOVERY,
            disposition=(
                DecisionDisposition.REVIEW_REQUIRED
                if plan.requires_human_review
                else DecisionDisposition.ALLOW
            ),
            reason=plan.reason,
            action="recovery.resume",
            metadata={"safe_to_resume": plan.safe_to_resume},
        ))
        if plan.disposition == RecoveryDisposition.COMPLETED:
            raise ValueError(f"WorkUnit {work_unit_id} is already completed")
        if plan.requires_human_review:
            pending = ", ".join(plan.pending_tool_call_ids)
            raise RuntimeError(
                f"WorkUnit {work_unit_id} requires human review before resume; "
                f"pending tool calls: {pending}"
            )
        if not plan.safe_to_resume:
            raise ValueError(
                f"WorkUnit {work_unit_id} is not safely resumable: {plan.reason}"
            )
        work_unit.metadata["resume_count"] = int(work_unit.metadata.get("resume_count", 0)) + 1
        work_unit.metadata["resumed"] = True
        work_unit.metadata["resume_from_cursor"] = True
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
        """Run through the AGENT_EXECUTION_RUNTIME lifecycle while persisting every terminal state."""
        work_unit.metadata["cwd"] = str(project_root)
        if "source_identity" not in work_unit.metadata:
            identity = self.workspace_identity(project_root)
            if identity is not None:
                work_unit.metadata["source_identity"] = identity
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
                project_root=project_root,
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

    def load_checkpoint(self, work_unit_id: str, project_root: Path | None = None):
        """Load the durable checkpoint associated with a WorkUnit."""
        root = project_root or Path.cwd()
        return self.state_store(root).load_checkpoint(work_unit_id)

    def artifact_store(self, project_root: Path):
        """Return persistent artifact metadata storage for a project."""
        return ArtifactStore(project_root / ".multiagentos" / "artifacts")

    def openai_chat_agent(self, model: str | None = None):
        """Create the optional OpenAI Chat Agent adapter."""
        from integrations.openai.chat_agent import OpenAIChatAgentAdapter

        return OpenAIChatAgentAdapter(model=model)

    def chat_agent_registry(self):
        """Return the default provider-neutral Chat Agent registry."""
        return default_chat_agents()

    def project_chat_agent(self, project_root: Path):
        """Resolve the configured project Chat Agent from the provider-neutral registry."""
        config = load_chat_config(project_root)
        registry = self.chat_agent_registry()
        agent = registry.get(config.agent_id)
        return agent, config.model

    def project_chat_adapter(self, project_root: Path):
        """Resolve the configured Chat Agent to its provider adapter."""
        agent, model = self.project_chat_agent(project_root)
        return agent, resolve_project_chat_adapter(agent, model=model)

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
        """Translate a Chat Agent turn into a AGENT_EXECUTION_RUNTIME WorkUnit and Plan."""
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
        """Execute a Chat Agent turn through the AGENT_EXECUTION_RUNTIME lifecycle."""
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
        """Reload a durable checkpoint and resume a generic AGENT_EXECUTION_RUNTIME workflow."""
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
        """Return the AGENT_EXECUTION_RUNTIME-controlled multi-agent handoff workflow."""
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
        return self.orchestrator.run_workflow(
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
        """Run bounded Review -> Rework -> Review under AGENT_EXECUTION_RUNTIME authority."""
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
        if checkpoint.agent_ids and checkpoint.agent_ids != (developer.id, tester.id, *reviewer_ids):
            raise ValueError("resume agents do not match checkpoint context")
        if checkpoint.model_ids and not set(checkpoint.model_ids).issubset(available_models):
            raise ValueError("resume models do not match checkpoint context")
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
        """Invoke an MCP tool after applying the AGENT_EXECUTION_RUNTIME agent/profile policy."""
        from runtime.mcp.proxy import MCPToolProxy
        return MCPToolProxy(self.mcp_clients, self.mcp_authorizer(project_root)).call(request, agent, profile_id)


    def execute_work_unit_with_github_actions(
        self,
        work_unit: WorkUnit,
        *,
        local,
        project_root: Path,
        repository: str,
        operation: MissionOperation = MissionOperation.TEST,
        workflow: str = "execution-mission.yml",
        ref: str = "main",
        inputs: dict[str, str] | None = None,
        local_available: bool = True,
        force_remote: bool = False,
        prefer_local: bool = True,
    ) -> AutomaticExecutionResult:
        """Execute a WorkUnit locally first and use the real GitHub mission runtime as fallback."""
        root = Path(project_root).resolve()
        identity = self.git.identity(str(root))
        source_sha = identity.get("head") if identity else None
        if not isinstance(source_sha, str) or len(source_sha) != 40:
            raise ValueError("GitHub mission requires a local repository HEAD SHA")
        mission = ExecutionMission(
            id=f"mission-{work_unit.id}",
            repository=repository,
            source_sha=source_sha,
            workflow=workflow,
            operation=MissionOperation(operation),
            ref=ref,
            inputs=dict(inputs or {}),
            expected_artifacts=("execution-mission-evidence",),
        )
        mission.validate()
        work_unit.metadata["execution_mission"] = {
            "id": mission.id,
            "repository": mission.repository,
            "source_sha": mission.source_sha,
            "workflow": mission.workflow,
            "operation": mission.operation.value,
            "ref": mission.ref,
            "expected_artifacts": list(mission.expected_artifacts),
        }

        def remote(_work_unit: WorkUnit):
            current_identity = self.git.identity(str(root))
            if not current_identity or current_identity.get("head") != mission.source_sha:
                raise PermissionError("GitHub fallback source SHA no longer matches the local WorkUnit")
            if current_identity.get("dirty") is True:
                raise PermissionError("GitHub fallback requires a clean local worktree")
            result = self.github.run_actions_mission(mission)
            return result, result.evidence

        return self.execute_work_unit_with_route(
            work_unit,
            local=local,
            remote=remote,
            local_available=local_available,
            force_remote=force_remote,
            prefer_local=prefer_local,
            project_root=root,
        )

    def execute_work_unit_with_route(
        self,
        work_unit: WorkUnit,
        *,
        local,
        remote=None,
        local_available: bool = True,
        force_remote: bool = False,
        prefer_local: bool = True,
        project_root: Path | None = None,
    ) -> AutomaticExecutionResult:
        """Execute one WorkUnit local-first with a bounded remote fallback."""
        coordinator = AutomaticWorkUnitExecutor(
            allow_github_actions=self.policy.allow_github_actions,
        )
        root = project_root or Path.cwd()
        try:
            result = coordinator.execute(
                work_unit,
                local=local,
                remote=remote,
                local_available=local_available,
                force_remote=force_remote,
                prefer_local=prefer_local,
            )
        except Exception:
            # Persist FAILED/BLOCKED lifecycle state before propagating the error.
            self.state_store(root).save(work_unit)
            raise
        self.state_store(root).save(work_unit)
        return result


__all__ = ["AgentExecutionRuntime"]
