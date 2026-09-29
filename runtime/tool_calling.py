"""Provider-neutral AI tool-calling runtime."""
from __future__ import annotations
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol
from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelAdapter, ModelRequest, ModelResponse
from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind, SessionSpec, ToolRequest, ToolResult, ToolSideEffect, ToolSpec
from runtime.policy import ExecutionPolicy

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
    def __init__(self, policy: ExecutionPolicy | None = None) -> None:
        self.policy = policy or ExecutionPolicy()
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

    def execute(self, request: ToolRequest, *, granted_permissions: frozenset[str] = frozenset(), approved: bool = False) -> ToolResult:
        item = self._tools.get(request.tool_id)
        if item is None:
            return ToolResult(request.tool_id, False, error=f"tool not registered: {request.tool_id}")
        missing = item.spec.permissions - granted_permissions
        if missing:
            return ToolResult(item.spec.id, False, error=f"tool permission denied: missing={sorted(missing)}")
        capability = {ToolSideEffect.READ: None, ToolSideEffect.WRITE: "filesystem.write", ToolSideEffect.EXECUTE: "process", ToolSideEffect.NETWORK: "network"}[item.spec.side_effect]
        if capability and not self.policy.permits(capability):
            return ToolResult(item.spec.id, False, error=f"tool capability is disabled: {capability}")
        if capability and self.policy.requires_approval(capability) and not approved:
            return ToolResult(item.spec.id, False, error=f"explicit approval required for: {capability}")
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
    def __init__(self, *, models: dict[str, ModelSpec], adapters: dict[str, ModelAdapter], tools: ToolRuntime, max_rounds: int = 8) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds must be at least 1")
        self.models, self.adapters, self.tools, self.max_rounds = models, adapters, tools, max_rounds

    def execute(self, request: ModelRequest, *, model_id: str, session: SessionSpec | None = None, work_unit_id: str | None = None, granted_permissions: frozenset[str] = frozenset(), approved: bool = False) -> ToolCallingExecution:
        model = self.models[model_id]
        adapter = self.adapters[model_id]
        generate = getattr(adapter, "generate_with_tools", None)
        if not callable(generate):
            raise ToolExecutionError(f"model adapter does not support tool calling: {model_id}")
        current, results = request, []
        history: list[dict[str, object]] = []
        for round_number in range(1, self.max_rounds + 1):
            response = generate(model, current, self.tools.specs())
            calls = self._normalize_calls(response.metadata.get("tool_calls", ()))
            if not calls:
                return ToolCallingExecution(response, model_id, round_number, tuple(results))
            round_results = []
            for call in calls:
                result = self.tools.execute(
                    ToolRequest(call["tool_id"], call["arguments"], session_id=session.id if session else None, work_unit_id=work_unit_id, metadata={"call_id": call["call_id"]}),
                    granted_permissions=granted_permissions, approved=approved,
                )
                results.append(result)
                round_results.append({"call_id": call["call_id"], "tool_id": result.tool_id, "ok": result.ok, "output": result.output, "error": result.error})
            history.append({"tool_calls": calls, "tool_results": tuple(round_results)})
            metadata = dict(current.metadata)
            metadata["tool_results"] = tuple(round_results)
            metadata["tool_history"] = tuple(history)
            current = ModelRequest(prompt=current.prompt, system=current.system, metadata=metadata)
        raise ToolExecutionError(f"tool calling exceeded maximum rounds: {self.max_rounds}")

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
            out.append({"call_id": str(item.get("call_id", item.get("id", f"call-{i+1}"))), "tool_id": tool_id, "arguments": dict(args)})
        return tuple(out)
