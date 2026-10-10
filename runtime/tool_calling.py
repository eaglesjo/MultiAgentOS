"""Provider-neutral AI tool-calling runtime."""
from __future__ import annotations
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import uuid4
from core.contracts.ai import ModelSpec
from core.contracts.approval import ApprovalGrant
from core.contracts.execution_limits import ExecutionBudget, RateLimit, LimitDisposition
from core.execution_limits import ExecutionLimitStore
from core.contracts.model_runtime import ModelAdapter, ModelRequest, ModelResponse
from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind, SessionSpec, ToolRequest, ToolResult, ToolSideEffect, ToolSpec
from runtime.policy import ExecutionPolicy
from core.contracts.replay import ReplayDisposition, ReplayPolicy
from core.contracts.tool_ledger import ToolInvocationRecord, ToolInvocationState
from core.contracts.execution_cursor import ExecutionCursor
from core.contracts.policy_decision import DecisionCategory, DecisionDisposition, PolicyDecision
from core.policy_decision import PolicyDecisionStore

class ToolExecutionError(RuntimeError):
    pass

class ToolHandler(Protocol):
    def __call__(self, request: ToolRequest) -> object: ...

@dataclass(frozen=True)
class RegisteredTool:
    spec: ToolSpec
    handler: ToolHandler

class ToolRuntime:
    """Central registry and policy boundary for normalized tool calls."""
    def __init__(self, policy: ExecutionPolicy | None = None, decision_store: PolicyDecisionStore | None = None) -> None:
        self.policy = policy or ExecutionPolicy()
        self.decision_store = decision_store
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if not spec.id.strip():
            raise ValueError("tool id must not be empty")
        if spec.id in self._tools:
            raise ValueError(f"tool already registered: {spec.id}")
        self._tools[spec.id] = RegisteredTool(spec, handler)

    def specs(self) -> tuple[ToolSpec, ...]:
        return tuple(item.spec for item in self._tools.values())

    def unregister(self, tool_id: str) -> None:
        """Remove a registered tool from the current scoped runtime."""
        self._tools.pop(tool_id, None)

    def execute(self, request: ToolRequest, *, granted_permissions: frozenset[str] = frozenset(), approved: bool = False, approval: ApprovalGrant | None = None) -> ToolResult:
        item = self._tools.get(request.tool_id)
        if item is None:
            return ToolResult(request.tool_id, False, error=f"tool not registered: {request.tool_id}")
        missing = item.spec.permissions - granted_permissions
        if missing:
            self._record_decision(request, DecisionCategory.PERMISSION, DecisionDisposition.DENY, f"missing permissions: {sorted(missing)}", action=item.spec.id)
            return ToolResult(item.spec.id, False, error=f"tool permission denied: missing={sorted(missing)}")
        capability = (
            "github.actions"
            if "github.actions" in item.spec.permissions
            else {
                ToolSideEffect.READ: None,
                ToolSideEffect.WRITE: "filesystem.write",
                ToolSideEffect.EXECUTE: "process",
                ToolSideEffect.NETWORK: "network",
            }[item.spec.side_effect]
        )
        if capability and not self.policy.permits(capability):
            self._record_decision(request, DecisionCategory.CAPABILITY, DecisionDisposition.DENY, f"capability disabled: {capability}", action=item.spec.id)
            return ToolResult(item.spec.id, False, error=f"tool capability is disabled: {capability}")
        if self.policy.requires_approval(item.spec.id, capability):
            # The legacy `approved` flag is not scoped evidence and must never bypass a grant.
            valid = self.policy.approval_valid(approval, action=item.spec.id, capability=capability, work_unit_id=request.work_unit_id, session_id=request.session_id)
            self._record_decision(request, DecisionCategory.APPROVAL, DecisionDisposition.ALLOW if valid else DecisionDisposition.DENY, "explicit approval accepted" if valid else f"explicit approval required for: {item.spec.id}", action=item.spec.id)
            if not valid:
                return ToolResult(item.spec.id, False, error=f"explicit approval required for: {item.spec.id}")
        return self._execute_handler(item, request)

    def _record_decision(self, request: ToolRequest, category: DecisionCategory, disposition: DecisionDisposition, reason: str, *, action: str | None = None) -> None:
        if self.decision_store is None or request.work_unit_id is None:
            return
        self.decision_store.append(PolicyDecision(work_unit_id=request.work_unit_id, category=category, disposition=disposition, reason=reason, action=action, session_id=request.session_id))

    def _execute_handler(self, item: RegisteredTool, request: ToolRequest) -> ToolResult:
        try:
            output = item.handler(request)
        except Exception as exc:
            return ToolResult(item.spec.id, False, error=str(exc))
        return ToolResult(item.spec.id, True, output=output, metadata={"side_effect": item.spec.side_effect.value})

class ToolCallingAdapter(Protocol):
    def generate_with_tools(self, model: ModelSpec, request: ModelRequest, tools: tuple[ToolSpec, ...]) -> ModelResponse: ...

@dataclass(frozen=True)
class ToolCallingExecution:
    response: ModelResponse
    model_id: str
    rounds: int
    tool_results: tuple[ToolResult, ...]

class ToolCallingRuntime:
    """Execute normalized model tool calls until the model returns a final response."""
    def __init__(self, *, models: dict[str, ModelSpec], adapters: dict[str, ModelAdapter], tools: ToolRuntime, max_rounds: int = 8, event_sink: Callable[[RuntimeEvent], None] | None = None, ledger_store: object | None = None, cursor_store: object | None = None, agent_id: str = "unknown", limit_store: ExecutionLimitStore | None = None, execution_budget: ExecutionBudget | None = None, rate_limit: RateLimit | None = None, decision_store: PolicyDecisionStore | None = None) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        self.models, self.adapters, self.tools, self.max_rounds, self.event_sink = models, adapters, tools, max_rounds, event_sink
        self.ledger_store = ledger_store
        self.cursor_store = cursor_store
        self.agent_id = agent_id
        self.limit_store = limit_store
        self.execution_budget = execution_budget
        self.rate_limit = rate_limit
        self.decision_store = decision_store

    def execute(self, request: ModelRequest, *, model_id: str, session: SessionSpec | None = None, work_unit_id: str | None = None, granted_permissions: frozenset[str] = frozenset(), approved: bool = False, approval: ApprovalGrant | None = None, start_round: int = 1, initial_cursor_sequence: int = 0, initial_conversation_revision: int = 0) -> ToolCallingExecution:
        model = self.models[model_id]
        adapter = self.adapters[model_id]
        generate = getattr(adapter, "generate_with_tools", None)
        if not callable(generate):
            raise ToolExecutionError(f"model adapter does not support tool calling: {model_id}")
        current, results = request, []
        history: list[dict[str, object]] = list(request.metadata.get("tool_history", ()))
        execution_audit = request.metadata.get("execution_decision")
        if not isinstance(execution_audit, dict):
            execution_audit = {}
        decision_id = execution_audit.get("decision_id")
        audit_agent_id = execution_audit.get("agent_id", self.agent_id)
        audit_model_id = execution_audit.get("model_id", model_id)
        cursor_sequence = initial_cursor_sequence
        conversation_revision = initial_conversation_revision
        for offset in range(self.max_rounds):
            round_number = start_round + offset
            if self.limit_store is not None and work_unit_id is not None and self.execution_budget is not None:
                decision = self.limit_store.check_round(work_unit_id, budget=self.execution_budget)
                if self.decision_store is not None:
                    self.decision_store.append(PolicyDecision(
                        work_unit_id=work_unit_id,
                        category=DecisionCategory.BUDGET,
                        disposition=DecisionDisposition.ALLOW if decision.disposition is LimitDisposition.ALLOW else DecisionDisposition.DENY,
                        reason=decision.reason,
                        action="round",
                    ))
                if decision.disposition is LimitDisposition.DENY:
                    raise ToolExecutionError(decision.reason)
                self.limit_store.record_round(work_unit_id)
            cursor_sequence += 1
            if self.cursor_store is not None and work_unit_id is not None:
                self.cursor_store.save_cursor(ExecutionCursor(
                    work_unit_id=work_unit_id,
                    event_sequence=cursor_sequence,
                    round_number=round_number,
                    agent_id=self.agent_id,
                    model_id=model_id,
                    conversation_revision=conversation_revision,
                ))
                conversation_revision = self.cursor_store.append_message(
                    work_unit_id,
                    role="request",
                    round_number=round_number,
                    content=request.prompt,
                    metadata={"system": request.system, "request": request.metadata},
                )
            if self.event_sink is not None:
                self.event_sink(RuntimeEvent(kind=RuntimeEventKind.REQUEST, session_id=session.id if session else None, work_unit_id=work_unit_id, payload={"model_id": model_id, "round": round_number}))
            response = generate(model, current, self.tools.specs())
            calls = self._normalize_calls(response.metadata.get("tool_calls", ()))
            if self.cursor_store is not None and work_unit_id is not None:
                cursor_sequence += 1
                conversation_revision = self.cursor_store.append_message(
                    work_unit_id,
                    role="assistant",
                    round_number=round_number,
                    content=response.text,
                    metadata={"model_id": response.model_id, "response": response.metadata},
                )
                self.cursor_store.save_cursor(ExecutionCursor(
                    work_unit_id=work_unit_id,
                    event_sequence=cursor_sequence,
                    round_number=round_number,
                    agent_id=self.agent_id,
                    model_id=model_id,
                    conversation_revision=conversation_revision,
                    next_tool_call_id=calls[0]["call_id"] if calls else None,
                ))
            if self.event_sink is not None:
                self.event_sink(RuntimeEvent(kind=RuntimeEventKind.MESSAGE, session_id=session.id if session else None, work_unit_id=work_unit_id, payload={"model_id": model_id, "round": round_number, "tool_call_count": len(calls)}))
            if not calls:
                if self.event_sink is not None:
                    self.event_sink(RuntimeEvent(kind=RuntimeEventKind.COMPLETED, session_id=session.id if session else None, work_unit_id=work_unit_id, payload={"model_id": model_id, "rounds": round_number}))
                return ToolCallingExecution(response, model_id, round_number, tuple(results))
            round_results = []
            for index, call in enumerate(calls):
                invocation_id = f"inv-{uuid4().hex}"
                if self.limit_store is not None and work_unit_id is not None and self.execution_budget is not None:
                    decision = self.limit_store.check_tool_call(work_unit_id, budget=self.execution_budget, rate_limit=self.rate_limit)
                    category = DecisionCategory.RATE_LIMIT if self.rate_limit is not None and "rate limit" in decision.reason else DecisionCategory.BUDGET
                    if self.decision_store is not None:
                        self.decision_store.append(PolicyDecision(
                            work_unit_id=work_unit_id,
                            category=category,
                            disposition=DecisionDisposition.ALLOW if decision.disposition is LimitDisposition.ALLOW else DecisionDisposition.DENY,
                            reason=decision.reason,
                            action="tool_call",
                        ))
                    if decision.disposition is LimitDisposition.DENY:
                        raise ToolExecutionError(decision.reason)
                    self.limit_store.record_tool_call(work_unit_id, rate_limit=self.rate_limit)
                if self.cursor_store is not None and work_unit_id is not None:
                    cursor_sequence += 1
                    self.cursor_store.save_cursor(ExecutionCursor(
                        work_unit_id=work_unit_id,
                        event_sequence=cursor_sequence,
                        round_number=round_number,
                        agent_id=self.agent_id,
                        model_id=model_id,
                        conversation_revision=conversation_revision,
                        next_tool_call_id=call["call_id"],
                    ))
                policy = self._replay_policy(call["tool_id"])
                idempotency_key = str(call.get("idempotency_key") or invocation_id)
                if self.ledger_store is not None and work_unit_id is not None:
                    existing = self.ledger_store.find_by_idempotency_key(work_unit_id, idempotency_key)
                    if existing:
                        latest = existing[-1]
                        raise ToolExecutionError(
                            f"idempotency key already used for tool invocation: {idempotency_key} "
                            f"(state={latest.state.value}, tool={latest.tool_id})"
                        )
                    self.ledger_store.append(ToolInvocationRecord(
                        invocation_id=invocation_id,
                        work_unit_id=work_unit_id,
                        tool_id=call["tool_id"],
                        arguments=call["arguments"],
                        call_id=call["call_id"],
                        state=ToolInvocationState.REQUESTED,
                        replay_policy=policy,
                        sequence=self.ledger_store.next_sequence(work_unit_id),
                        idempotency_key=idempotency_key,
                        decision_id=decision_id if isinstance(decision_id, str) else None,
                        agent_id=audit_agent_id if isinstance(audit_agent_id, str) else None,
                        model_id=audit_model_id if isinstance(audit_model_id, str) else None,
                    ))
                if self.event_sink is not None:
                    self.event_sink(RuntimeEvent(kind=RuntimeEventKind.TOOL_CALL, session_id=session.id if session else None, work_unit_id=work_unit_id, payload={"call_id": call["call_id"], "invocation_id": invocation_id, "tool_id": call["tool_id"], "arguments": call["arguments"], "round": round_number, "decision_id": decision_id, "agent_id": audit_agent_id, "model_id": audit_model_id}))
                if self.ledger_store is not None and work_unit_id is not None:
                    self.ledger_store.append(ToolInvocationRecord(
                        invocation_id=invocation_id,
                        work_unit_id=work_unit_id,
                        tool_id=call["tool_id"],
                        arguments=call["arguments"],
                        state=ToolInvocationState.STARTED,
                        replay_policy=policy,
                        sequence=self.ledger_store.next_sequence(work_unit_id),
                        idempotency_key=idempotency_key,
                        decision_id=decision_id if isinstance(decision_id, str) else None,
                        agent_id=audit_agent_id if isinstance(audit_agent_id, str) else None,
                        model_id=audit_model_id if isinstance(audit_model_id, str) else None,
                    ))
                result = self.tools.execute(
                    ToolRequest(call["tool_id"], call["arguments"], session_id=session.id if session else None, work_unit_id=work_unit_id, metadata={"call_id": call["call_id"], "invocation_id": invocation_id, "idempotency_key": idempotency_key}),
                    granted_permissions=granted_permissions, approved=approved, approval=approval,
                )
                results.append(result)
                terminal_state = ToolInvocationState.COMPLETED if result.ok else ToolInvocationState.FAILED
                if self.ledger_store is not None and work_unit_id is not None:
                    self.ledger_store.append(ToolInvocationRecord(
                        invocation_id=invocation_id,
                        work_unit_id=work_unit_id,
                        tool_id=call["tool_id"],
                        arguments=call["arguments"],
                        state=terminal_state,
                        replay_policy=policy,
                        sequence=self.ledger_store.next_sequence(work_unit_id),
                        result_reference=invocation_id if result.ok else None,
                        error=result.error,
                        idempotency_key=idempotency_key,
                        decision_id=decision_id if isinstance(decision_id, str) else None,
                        agent_id=audit_agent_id if isinstance(audit_agent_id, str) else None,
                        model_id=audit_model_id if isinstance(audit_model_id, str) else None,
                    ))
                if self.event_sink is not None:
                    self.event_sink(RuntimeEvent(kind=RuntimeEventKind.TOOL_RESULT, session_id=session.id if session else None, work_unit_id=work_unit_id, payload={"call_id": call["call_id"], "invocation_id": invocation_id, "tool_id": result.tool_id, "ok": result.ok, "output": result.output, "error": result.error, "round": round_number, "decision_id": decision_id, "agent_id": audit_agent_id, "model_id": audit_model_id}))
                if self.cursor_store is not None and work_unit_id is not None:
                    cursor_sequence += 1
                    conversation_revision = self.cursor_store.append_message(
                        work_unit_id,
                        role="tool",
                        round_number=round_number,
                        content=result.output,
                        metadata={"call_id": call["call_id"], "invocation_id": invocation_id, "tool_id": result.tool_id, "ok": result.ok, "error": result.error},
                    )
                    next_call_id = calls[index + 1]["call_id"] if index + 1 < len(calls) else None
                    self.cursor_store.save_cursor(ExecutionCursor(
                        work_unit_id=work_unit_id,
                        event_sequence=cursor_sequence,
                        round_number=round_number,
                        agent_id=self.agent_id,
                        model_id=model_id,
                        conversation_revision=conversation_revision,
                        next_tool_call_id=next_call_id,
                    ))
                round_results.append({"call_id": call["call_id"], "tool_id": result.tool_id, "ok": result.ok, "output": result.output, "error": result.error, "invocation_id": invocation_id})
            history.append({"tool_calls": calls, "tool_results": tuple(round_results)})
            metadata = dict(current.metadata)
            metadata["tool_results"] = tuple(round_results)
            metadata["tool_history"] = tuple(history)
            current = ModelRequest(prompt=current.prompt, system=current.system, metadata=metadata)
        raise ToolExecutionError(f"tool calling exceeded maximum rounds: {self.max_rounds}")

    def resume(self, request: ModelRequest, *, model_id: str, work_unit_id: str, session: SessionSpec | None = None, granted_permissions: frozenset[str] = frozenset(), approved: bool = False) -> ToolCallingExecution:
        """Resume a persisted tool-calling round from its durable cursor."""
        if self.cursor_store is None:
            raise ToolExecutionError("durable cursor store is required for resume")
        try:
            cursor = self.cursor_store.load_cursor(work_unit_id)
        except FileNotFoundError:
            return self.execute(
                request,
                model_id=model_id,
                session=session,
                work_unit_id=work_unit_id,
                granted_permissions=granted_permissions,
                approved=approved,
            )
        messages = self.cursor_store.load_messages(work_unit_id)
        if not messages:
            return self.execute(
                request,
                model_id=model_id,
                session=session,
                work_unit_id=work_unit_id,
                granted_permissions=granted_permissions,
                approved=approved,
                start_round=cursor.round_number,
                initial_cursor_sequence=cursor.event_sequence,
                initial_conversation_revision=cursor.conversation_revision,
            )

        assistant = next(
            (
                item for item in reversed(messages)
                if item.get("role") == "assistant"
                and int(item.get("round_number", 0)) == cursor.round_number
            ),
            None,
        )
        if assistant is None:
            return self.execute(
                request,
                model_id=model_id,
                session=session,
                work_unit_id=work_unit_id,
                granted_permissions=granted_permissions,
                approved=approved,
                start_round=cursor.round_number,
                initial_cursor_sequence=cursor.event_sequence,
                initial_conversation_revision=cursor.conversation_revision,
            )

        response_meta = assistant.get("metadata", {}).get("response", {})
        calls = (
            self._normalize_calls(response_meta.get("tool_calls", ()))
            if isinstance(response_meta, dict)
            else ()
        )
        if not calls:
            response = ModelResponse(
                text=str(assistant.get("content", "")),
                model_id=str(
                    response_meta.get("model_id", model_id)
                    if isinstance(response_meta, dict)
                    else model_id
                ),
                metadata=dict(response_meta) if isinstance(response_meta, dict) else {},
            )
            if self.event_sink is not None:
                self.event_sink(RuntimeEvent(
                    kind=RuntimeEventKind.COMPLETED,
                    session_id=session.id if session else None,
                    work_unit_id=work_unit_id,
                    payload={"model_id": response.model_id, "rounds": cursor.round_number, "resumed": True},
                ))
            return ToolCallingExecution(response, response.model_id, cursor.round_number, tuple())

        completed_messages = {
            str(item.get("metadata", {}).get("call_id"))
            for item in messages
            if item.get("role") == "tool"
            and int(item.get("round_number", 0)) == cursor.round_number
        }
        pending = [call for call in calls if call["call_id"] not in completed_messages]
        conversation_revision = cursor.conversation_revision
        next_cursor_sequence = cursor.event_sequence
        round_results: list[dict[str, object]] = []

        if pending:
            for call in pending:
                ledger_records = (
                    self.ledger_store.unresolved(work_unit_id)
                    if self.ledger_store is not None
                    else ()
                )
                record = next(
                    (item for item in ledger_records if item.call_id == call["call_id"]),
                    None,
                )
                if record is None:
                    raise ToolExecutionError(
                        f"missing durable invocation for pending call: {call['call_id']}"
                    )
                if record.state == ToolInvocationState.REQUESTED:
                    self.ledger_store.append(ToolInvocationRecord(
                        invocation_id=record.invocation_id,
                        work_unit_id=work_unit_id,
                        tool_id=record.tool_id,
                        arguments=record.arguments,
                        state=ToolInvocationState.STARTED,
                        replay_policy=record.replay_policy,
                        sequence=self.ledger_store.next_sequence(work_unit_id),
                        call_id=record.call_id,
                        idempotency_key=record.idempotency_key,
                        decision_id=record.decision_id,
                        agent_id=record.agent_id,
                        model_id=record.model_id,
                    ))
                audit_agent_id = record.agent_id or self.agent_id
                audit_model_id = record.model_id or model_id
                if record.replay_policy.disposition is ReplayDisposition.NEVER:
                    raise ToolExecutionError(
                        f"tool invocation cannot be replayed: {record.tool_id}"
                    )
                if record.replay_policy.requires_human_review and not approved:
                    raise ToolExecutionError(
                        f"human recovery approval required to replay tool: {record.tool_id}"
                    )
                if self.event_sink is not None:
                    self.event_sink(RuntimeEvent(
                        kind=RuntimeEventKind.TOOL_CALL,
                        session_id=session.id if session else None,
                        work_unit_id=work_unit_id,
                        payload={
                            "call_id": record.call_id,
                            "invocation_id": record.invocation_id,
                            "tool_id": record.tool_id,
                            "idempotency_key": record.idempotency_key,
                            "decision_id": record.decision_id,
                            "agent_id": audit_agent_id,
                            "model_id": audit_model_id,
                            "resumed": True,
                        },
                    ))
                result = self.tools.execute(
                    ToolRequest(
                        call["tool_id"],
                        call["arguments"],
                        session_id=session.id if session else None,
                        work_unit_id=work_unit_id,
                        metadata={
                            "call_id": call["call_id"],
                            "invocation_id": record.invocation_id,
                            "idempotency_key": record.idempotency_key,
                            "decision_id": record.decision_id,
                            "agent_id": audit_agent_id,
                            "model_id": audit_model_id,
                            "resume": True,
                        },
                    ),
                    granted_permissions=granted_permissions,
                    approved=approved,
                )
                terminal = ToolInvocationState.COMPLETED if result.ok else ToolInvocationState.FAILED
                self.ledger_store.append(ToolInvocationRecord(
                    invocation_id=record.invocation_id,
                    work_unit_id=work_unit_id,
                    tool_id=record.tool_id,
                    arguments=record.arguments,
                    state=terminal,
                    replay_policy=record.replay_policy,
                    sequence=self.ledger_store.next_sequence(work_unit_id),
                    call_id=record.call_id,
                    result_reference=record.invocation_id if result.ok else None,
                    error=result.error,
                    idempotency_key=record.idempotency_key,
                    decision_id=record.decision_id,
                    agent_id=record.agent_id,
                    model_id=record.model_id,
                ))
                payload = {
                    "call_id": call["call_id"],
                    "tool_id": result.tool_id,
                    "ok": result.ok,
                    "output": result.output,
                    "error": result.error,
                    "invocation_id": record.invocation_id,
                    "idempotency_key": record.idempotency_key,
                    "decision_id": record.decision_id,
                    "agent_id": audit_agent_id,
                    "model_id": audit_model_id,
                    "resumed": True,
                }
                if self.event_sink is not None:
                    self.event_sink(RuntimeEvent(
                        kind=RuntimeEventKind.TOOL_RESULT,
                        session_id=session.id if session else None,
                        work_unit_id=work_unit_id,
                        payload=payload,
                    ))
                round_results.append(payload)
                conversation_revision = self.cursor_store.append_message(
                    work_unit_id,
                    role="tool",
                    round_number=cursor.round_number,
                    content=result.output,
                    metadata=payload,
                )

        messages = self.cursor_store.load_messages(work_unit_id)
        history: list[dict[str, object]] = []
        for round_number in sorted(
            {
                int(item.get("round_number", 0))
                for item in messages
                if item.get("role") == "assistant"
            }
        ):
            assistant_item = next(
                item
                for item in messages
                if item.get("role") == "assistant"
                and int(item.get("round_number", 0)) == round_number
            )
            meta = assistant_item.get("metadata", {}).get("response", {})
            round_calls = self._normalize_calls(meta.get("tool_calls", ())) if isinstance(meta, dict) else ()
            round_tool_results = [
                item.get("metadata", {})
                for item in messages
                if item.get("role") == "tool"
                and int(item.get("round_number", 0)) == round_number
            ]
            if round_calls:
                history.append({
                    "tool_calls": round_calls,
                    "tool_results": tuple(round_tool_results),
                })

        request = ModelRequest(
            prompt=request.prompt,
            system=request.system,
            metadata={
                **dict(request.metadata),
                "tool_results": tuple(round_results),
                "tool_history": tuple(history),
            },
        )
        if pending:
            next_cursor_sequence += 1
            self.cursor_store.save_cursor(ExecutionCursor(
                work_unit_id=work_unit_id,
                event_sequence=next_cursor_sequence,
                round_number=cursor.round_number,
                agent_id=cursor.agent_id,
                model_id=cursor.model_id,
                conversation_revision=conversation_revision,
                next_tool_call_id=None,
            ))

        return self.execute(
            request,
            model_id=model_id,
            session=session,
            work_unit_id=work_unit_id,
            granted_permissions=granted_permissions,
            approved=approved,
            start_round=cursor.round_number + 1,
            initial_cursor_sequence=next_cursor_sequence,
            initial_conversation_revision=conversation_revision,
        )

    def events(self, request: ModelRequest, *, model_id: str, session: SessionSpec | None = None, work_unit_id: str | None = None, granted_permissions: frozenset[str] = frozenset(), approved: bool = False) -> Iterator[RuntimeEvent]:
        sequence = 0
        def emit(kind: RuntimeEventKind, payload: object) -> RuntimeEvent:
            nonlocal sequence
            sequence += 1
            return RuntimeEvent(kind=kind, session_id=session.id if session else None, work_unit_id=work_unit_id, payload=payload, sequence=sequence)
        yield emit(RuntimeEventKind.REQUEST, {"model_id": model_id})
        result = self.execute(request, model_id=model_id, session=session, work_unit_id=work_unit_id, granted_permissions=granted_permissions, approved=approved)
        for item in result.tool_results:
            yield emit(RuntimeEventKind.TOOL_CALL, {"tool_id": item.tool_id})
            yield emit(RuntimeEventKind.TOOL_RESULT, item)
        yield emit(RuntimeEventKind.MESSAGE, {"model_id": result.model_id, "text": result.response.text})
        yield emit(RuntimeEventKind.COMPLETED, {"model_id": result.model_id, "rounds": result.rounds})

    @staticmethod
    def _replay_policy(tool_id: str) -> ReplayPolicy:
        if tool_id.startswith("filesystem.read") or tool_id in {"git.status", "git.diff"}:
            return ReplayPolicy(ReplayDisposition.SAFE, reason="read-only tool")
        return ReplayPolicy(
            ReplayDisposition.REVIEW_REQUIRED,
            reason="tool may have an external or persistent side effect",
        )

    @staticmethod
    def _normalize_calls(value: object) -> tuple[dict[str, object], ...]:
        if not isinstance(value, (list, tuple)):
            return ()
        out = []
        for i, item in enumerate(value):
            if not isinstance(item, dict):
                raise ToolExecutionError("tool call must be an object")
            tool_id = item.get("tool_id", item.get("name"))
            if not isinstance(tool_id, str) or not tool_id:
                raise ToolExecutionError("tool call is missing tool_id")
            args = item.get("arguments", {})
            if not isinstance(args, dict):
                raise ToolExecutionError(f"tool call arguments must be an object: {tool_id}")
            out.append({
                "call_id": str(item.get("call_id", item.get("id", f"call-{i+1}"))),
                "tool_id": tool_id,
                "arguments": dict(args),
                "idempotency_key": item.get("idempotency_key"),
            })
        return tuple(out)
