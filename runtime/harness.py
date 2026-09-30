"""Project-scoped execution harness for the Agent Execution Runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.contracts.agent_execution_runtime import RuntimeEvent
from core.contracts.memory import MemoryKind, ProjectMemory
from core.approval import ApprovalStore
from core.policy_decision import PolicyDecisionStore
from core.execution_state import ExecutionStateStore
from core.execution_limits import ExecutionLimitStore
from core.contracts.execution_limits import ExecutionBudget, RateLimit
from core.memory import ProjectMemoryStore
from runtime.model_control import ModelControlPlane
from runtime.observability import ExecutionObservability, ExecutionEvidenceSummary
from core.recovery_audit import RecoveryAuditStore
from core.state import RuntimeEventStore
from core.tool_ledger import ToolInvocationStore
from runtime.builtin_tools import BuiltinToolBindings
from runtime.policy import ExecutionPolicy
from runtime.repository_tools import GitToolBindings, MCPToolBindings
from runtime.tool_calling import ToolRuntime


@dataclass
class ExecutionHarness:
    """Own the project-scoped runtime resources used by one durable execution."""

    project_root: Path
    policy: ExecutionPolicy
    tool_runtime: ToolRuntime
    event_store: RuntimeEventStore
    ledger_store: ToolInvocationStore
    execution_state_store: ExecutionStateStore
    recovery_audit_store: RecoveryAuditStore
    memory_store: ProjectMemoryStore
    model_control: ModelControlPlane
    observability: ExecutionObservability
    approval_store: ApprovalStore
    execution_limit_store: ExecutionLimitStore
    decision_store: PolicyDecisionStore

    @classmethod
    def create(
        cls,
        project_root: Path,
        *,
        policy: ExecutionPolicy | None = None,
        apply_changes: bool = False,
    ) -> "ExecutionHarness":
        root = Path(project_root).resolve()
        effective_policy = policy or ExecutionPolicy()
        durable_root = root / ".multiagentos"
        decision_store = PolicyDecisionStore(durable_root / "decisions")
        tool_runtime = ToolRuntime(effective_policy, decision_store=decision_store)
        BuiltinToolBindings(str(root), tool_runtime)
        GitToolBindings(str(root), tool_runtime)
        if not apply_changes:
            tool_runtime.unregister("patch.apply")
        return cls(
            project_root=root,
            policy=effective_policy,
            tool_runtime=tool_runtime,
            event_store=RuntimeEventStore(durable_root / "events"),
            ledger_store=ToolInvocationStore(durable_root / "tool-ledger"),
            execution_state_store=ExecutionStateStore(durable_root / "execution-state"),
            recovery_audit_store=RecoveryAuditStore(durable_root / "recovery"),
            memory_store=ProjectMemoryStore(durable_root / "memory"),
            model_control=ModelControlPlane(root),
            observability=ExecutionObservability(root),
            approval_store=ApprovalStore(durable_root / "approvals"),
            execution_limit_store=ExecutionLimitStore(durable_root / "limits"),
            decision_store=decision_store,
        )

    def register_mcp_client(self, client) -> None:
        """Expose one connected MCP server through the scoped tool runtime."""
        MCPToolBindings(self.tool_runtime, client).register_tools()

    def event_sink(self) -> Callable[[RuntimeEvent], None]:
        """Return the durable event sink for model/tool execution."""
        return self.event_store.append

    def remember(self, content: str, *, kind: MemoryKind = MemoryKind.NOTE, source: str = "runtime", metadata: dict[str, object] | None = None) -> ProjectMemory:
        """Persist project context through the harness security boundary."""
        return self.memory_store.append(content, kind=kind, source=source, metadata=metadata)

    def recall(self, query: str = "", *, limit: int = 20) -> tuple[ProjectMemory, ...]:
        """Retrieve bounded project context without touching execution journals."""
        return self.memory_store.search(query, limit=limit)



    def check_tool_limit(self, work_unit_id: str, *, budget: ExecutionBudget, rate_limit: RateLimit | None = None):
        return self.execution_limit_store.check_tool_call(work_unit_id, budget=budget, rate_limit=rate_limit)

    def record_tool_call(self, work_unit_id: str, *, rate_limit: RateLimit | None = None) -> None:
        self.execution_limit_store.record_tool_call(work_unit_id, rate_limit=rate_limit)

    def check_round_limit(self, work_unit_id: str, *, budget: ExecutionBudget):
        return self.execution_limit_store.check_round(work_unit_id, budget=budget)

    def record_round(self, work_unit_id: str) -> None:
        self.execution_limit_store.record_round(work_unit_id)
