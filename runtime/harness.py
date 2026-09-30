"""Project-scoped execution harness for the Agent Execution Runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from core.contracts.agent_execution_runtime import RuntimeEvent
from core.contracts.memory import MemoryKind, ProjectMemory
from core.execution_state import ExecutionStateStore
from core.memory import ProjectMemoryStore
from runtime.model_control import ModelControlPlane
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
        tool_runtime = ToolRuntime(effective_policy)
        BuiltinToolBindings(str(root), tool_runtime)
        GitToolBindings(str(root), tool_runtime)
        if not apply_changes:
            tool_runtime.unregister("patch.apply")
        durable_root = root / ".multiagentos"
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
