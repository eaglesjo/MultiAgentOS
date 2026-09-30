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
from core.recovery_audit import RecoveryAuditStore
from core.contracts.recovery import RecoveryDecision, RecoveryDisposition
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
        self.recovery_audit_store = RecoveryAuditStore(durable_root / "recovery")

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

    def recover(
        self,
        work_unit_id: str,
        *,
        session_id: str | None = None,
        human_decision: str | None = None,
        notes: str = "",
    ):
        """Recover one interrupted MCP invocation using the existing durable replay contract."""
        from runtime.agent_execution_runtime import AgentExecutionRuntime

        runtime = AgentExecutionRuntime()
        plan = runtime.recovery_plan(self.project_root, work_unit_id)
        self.recovery_audit_store.append(
            plan,
            source_identity=runtime.workspace_identity(self.project_root),
        )
        if plan.disposition is RecoveryDisposition.COMPLETED:
            return {"work_unit_id": work_unit_id, "disposition": plan.disposition.value, "replayed": False}
        recovery_authorized = False
        if plan.disposition is RecoveryDisposition.REVIEW_REQUIRED:
            decision = human_decision.strip().lower() if isinstance(human_decision, str) else None
            if decision is None:
                self.decision_store.append(
                    PolicyDecision(
                        work_unit_id=work_unit_id,
                        category=DecisionCategory.RECOVERY,
                        disposition=DecisionDisposition.REVIEW_REQUIRED,
                        reason=plan.reason,
                        action="mcp.recover",
                        session_id=session_id,
                        metadata={"source": "mcp", "pending_tool_call_ids": list(plan.pending_tool_call_ids)},
                    )
                )
                return {"work_unit_id": work_unit_id, "disposition": plan.disposition.value, "replayed": False}

            authorization = runtime.resolve_recovery_review(
                self.project_root,
                work_unit_id,
                decision=RecoveryDecision(decision),
                notes=notes,
                session_id=session_id,
            )
            if not authorization.authorized:
                return {
                    "work_unit_id": work_unit_id,
                    "disposition": RecoveryDisposition.FAILED.value,
                    "replayed": False,
                    "human_decision": authorization.decision.value,
                }
            unresolved = self.ledger_store.unresolved(work_unit_id)
            if not unresolved:
                return {
                    "work_unit_id": work_unit_id,
                    "disposition": RecoveryDisposition.COMPLETED.value,
                    "replayed": False,
                    "human_decision": authorization.decision.value,
                }
            if len(unresolved) != 1:
                raise ValueError("MCP recovery supports exactly one unresolved direct tool invocation")
            recovery_authorized = True
            plan_safe_override = True
        else:
            plan_safe_override = False

        if plan.disposition is not RecoveryDisposition.RESUME or (not plan.safe_to_resume and not plan_safe_override):
            raise ValueError(f"MCP work unit is not safely resumable: {plan.reason}")

        unresolved = self.ledger_store.unresolved(work_unit_id)
        if not unresolved:
            raise ValueError("MCP recovery plan requested resume but no unresolved invocation exists")
        if len(unresolved) != 1:
            raise ValueError("MCP recovery supports exactly one unresolved direct tool invocation")
        record = unresolved[0]
        if not record.replay_safe and not recovery_authorized:
            raise ValueError("MCP invocation is not replay-safe")

        request = ToolRequest(
            record.tool_id,
            dict(record.arguments),
            session_id=session_id,
            work_unit_id=work_unit_id,
            metadata={
                "source": "mcp-recovery",
                "call_id": record.call_id,
                "invocation_id": record.invocation_id,
                "idempotency_key": record.idempotency_key,
            },
        )
        granted_permissions = frozenset(
            {
                "filesystem.write" if self.tool_runtime.policy.allow_filesystem_write else "",
                "process" if self.tool_runtime.policy.allow_process else "",
            }
        ) - {""}
        self.decision_store.append(
            PolicyDecision(
                work_unit_id=work_unit_id,
                category=DecisionCategory.RECOVERY,
                disposition=DecisionDisposition.ALLOW,
                reason="MCP recovery replay is explicitly safe and idempotency-keyed",
                action=record.tool_id,
                session_id=session_id,
                metadata={
                    "source": "mcp",
                    "invocation_id": record.invocation_id,
                    "idempotency_key": record.idempotency_key,
                },
            )
        )
        self._append_event(
            RuntimeEventKind.TOOL_CALL,
            work_unit_id,
            {
                "source": "mcp-recovery",
                "call_id": record.call_id,
                "invocation_id": record.invocation_id,
                "tool_id": record.tool_id,
                "arguments": dict(record.arguments),
                "idempotency_key": record.idempotency_key,
            },
            session_id=session_id,
        )
        result = self.tool_runtime.execute(
            request,
            granted_permissions=granted_permissions,
            approved=True,
        )
        terminal_state = ToolInvocationState.COMPLETED if result.ok else ToolInvocationState.FAILED
        result_reference = f"mcp:{record.invocation_id}" if result.ok else None
        self.ledger_store.append(
            ToolInvocationRecord(
                invocation_id=record.invocation_id,
                work_unit_id=work_unit_id,
                tool_id=record.tool_id,
                arguments=dict(record.arguments),
                state=terminal_state,
                replay_policy=record.replay_policy,
                sequence=self.ledger_store.next_sequence(work_unit_id),
                call_id=record.call_id,
                result_reference=result_reference,
                error=result.error,
                idempotency_key=record.idempotency_key,
            )
        )
        self._append_event(
            RuntimeEventKind.TOOL_RESULT,
            work_unit_id,
            {
                "source": "mcp-recovery",
                "call_id": record.call_id,
                "invocation_id": record.invocation_id,
                "tool_id": result.tool_id,
                "ok": result.ok,
                "error": result.error,
                "idempotency_key": record.idempotency_key,
            },
            session_id=session_id,
        )
        work_unit = self.work_store.load(work_unit_id)
        if result.ok:
            work_unit.transition(WorkStatus.COMPLETED)
            work_unit.metadata["result_reference"] = result_reference
            self._append_event(
                RuntimeEventKind.COMPLETED,
                work_unit_id,
                {
                    "source": "mcp-recovery",
                    "call_id": record.call_id,
                    "invocation_id": record.invocation_id,
                    "tool_id": record.tool_id,
                },
                session_id=session_id,
            )
        else:
            work_unit.transition(WorkStatus.FAILED)
            work_unit.metadata["error"] = result.error
        self.work_store.save(work_unit)
        return {
            "work_unit_id": work_unit_id,
            "disposition": RecoveryDisposition.COMPLETED.value if result.ok else RecoveryDisposition.FAILED.value,
            "replayed": True,
            "invocation_id": record.invocation_id,
            "idempotency_key": record.idempotency_key,
            "result": result,
        }

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
