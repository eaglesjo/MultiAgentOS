"""Durable execution bridge for direct MCP tool calls."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from core.contracts.agent_execution_runtime import (
    RuntimeEvent,
    RuntimeEventKind,
    ToolRequest,
)
from core.contracts.replay import ReplayDisposition, ReplayPolicy
from core.contracts.policy_decision import DecisionCategory, DecisionDisposition, PolicyDecision
from core.policy_decision import PolicyDecisionStore
from core.contracts.tool_ledger import ToolInvocationRecord, ToolInvocationState
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.state import RuntimeEventStore, WorkStateStore
from core.tool_ledger import ToolInvocationStore
from runtime.tool_calling import ToolRuntime


class MCPDurableExecutionBridge:
    """Wrap one MCP tool call in the Agent Execution Runtime durable evidence contract."""

    def __init__(self, project_root: Path, tool_runtime: ToolRuntime) -> None:
        self.project_root = Path(project_root).resolve()
        durable_root = self.project_root / ".multiagentos"
        self.tool_runtime = tool_runtime
        self.work_store = WorkStateStore(durable_root / "state")
        self.event_store = RuntimeEventStore(durable_root / "events")
        self.ledger_store = ToolInvocationStore(durable_root / "tool-ledger")
        self.decision_store = PolicyDecisionStore(durable_root / "decisions")

    def _replay_policy(self, tool_id: str) -> ReplayPolicy:
        if tool_id.startswith("filesystem.read") or tool_id in {"git.status", "git.diff"}:
            return ReplayPolicy(ReplayDisposition.SAFE, reason="read-only tool")
        return ReplayPolicy(
            ReplayDisposition.REVIEW_REQUIRED,
            reason="tool may have an external or persistent side effect",
        )

    def _append_event(
        self,
        kind: RuntimeEventKind,
        work_unit_id: str,
        payload: object,
        *,
        session_id: str | None = None,
    ) -> None:
        self.event_store.append(
            RuntimeEvent(
                kind=kind,
                session_id=session_id,
                work_unit_id=work_unit_id,
                payload=payload,
            )
        )

    def call(
        self,
        name: str,
        arguments: dict[str, object],
        *,
        session_id: str | None = None,
    ):
        work_unit_id = f"mcp-{uuid4().hex}"
        invocation_id = f"inv-{uuid4().hex}"
        call_id = f"call-{uuid4().hex}"
        idempotency_key = invocation_id
        replay_policy = self._replay_policy(name)

        work_unit = WorkUnit(
            id=work_unit_id,
            objective=f"MCP tools/call: {name}",
            metadata={
                "source": "mcp",
                "tool_id": name,
                "session_id": session_id,
                "call_id": call_id,
                "invocation_id": invocation_id,
            },
        )
        work_unit.transition(WorkStatus.EXECUTING)
        self.work_store.save(work_unit)

        self.decision_store.append(
            PolicyDecision(
                work_unit_id=work_unit_id,
                category=DecisionCategory.CAPABILITY,
                disposition=DecisionDisposition.ALLOW,
                reason="MCP tool call entered the Agent Execution Runtime durable boundary",
                action=name,
                session_id=session_id,
                metadata={
                    "source": "mcp",
                    "replay_disposition": replay_policy.disposition.value,
                },
            )
        )

        self._append_event(
            RuntimeEventKind.REQUEST,
            work_unit_id,
            {
                "source": "mcp",
                "tool_id": name,
                "call_id": call_id,
                "invocation_id": invocation_id,
            },
            session_id=session_id,
        )

        self.ledger_store.append(
            ToolInvocationRecord(
                invocation_id=invocation_id,
                work_unit_id=work_unit_id,
                tool_id=name,
                arguments=dict(arguments),
                state=ToolInvocationState.REQUESTED,
                replay_policy=replay_policy,
                sequence=self.ledger_store.next_sequence(work_unit_id),
                call_id=call_id,
                idempotency_key=idempotency_key,
            )
        )

        self._append_event(
            RuntimeEventKind.TOOL_CALL,
            work_unit_id,
            {
                "source": "mcp",
                "call_id": call_id,
                "invocation_id": invocation_id,
                "tool_id": name,
                "arguments": dict(arguments),
            },
            session_id=session_id,
        )

        self.ledger_store.append(
            ToolInvocationRecord(
                invocation_id=invocation_id,
                work_unit_id=work_unit_id,
                tool_id=name,
                arguments=dict(arguments),
                state=ToolInvocationState.STARTED,
                replay_policy=replay_policy,
                sequence=self.ledger_store.next_sequence(work_unit_id),
                call_id=call_id,
                idempotency_key=idempotency_key,
            )
        )

        request = ToolRequest(
            name,
            dict(arguments),
            session_id=session_id,
            work_unit_id=work_unit_id,
            metadata={
                "source": "mcp",
                "call_id": call_id,
                "invocation_id": invocation_id,
            },
        )
        granted_permissions = frozenset(
            {
                "filesystem.write"
                if self.tool_runtime.policy.allow_filesystem_write
                else "",
                "process" if self.tool_runtime.policy.allow_process else "",
            }
        ) - {""}

        result = self.tool_runtime.execute(
            request,
            granted_permissions=granted_permissions,
            approved=True,
        )

        if result.ok:
            terminal_state = ToolInvocationState.COMPLETED
            result_reference = f"mcp:{invocation_id}"
        else:
            terminal_state = ToolInvocationState.FAILED
            result_reference = None

        self.ledger_store.append(
            ToolInvocationRecord(
                invocation_id=invocation_id,
                work_unit_id=work_unit_id,
                tool_id=name,
                arguments=dict(arguments),
                state=terminal_state,
                replay_policy=replay_policy,
                sequence=self.ledger_store.next_sequence(work_unit_id),
                call_id=call_id,
                result_reference=result_reference,
                error=result.error,
                idempotency_key=idempotency_key,
            )
        )

        self._append_event(
            RuntimeEventKind.TOOL_RESULT,
            work_unit_id,
            {
                "source": "mcp",
                "call_id": call_id,
                "invocation_id": invocation_id,
                "tool_id": result.tool_id,
                "ok": result.ok,
                "error": result.error,
            },
            session_id=session_id,
        )

        if result.ok:
            work_unit.transition(WorkStatus.COMPLETED)
            work_unit.metadata["result_reference"] = result_reference
            self._append_event(
                RuntimeEventKind.COMPLETED,
                work_unit_id,
                {
                    "source": "mcp",
                    "call_id": call_id,
                    "invocation_id": invocation_id,
                    "tool_id": name,
                },
                session_id=session_id,
            )
        else:
            work_unit.transition(WorkStatus.FAILED)
            work_unit.metadata["error"] = result.error

        self.work_store.save(work_unit)
        return result


__all__ = ["MCPDurableExecutionBridge"]
