"""Provider-neutral runtime contracts for the VYRELON core."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ToolSideEffect(StrEnum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"


class RuntimeEventKind(StrEnum):
    REQUEST = "request"
    DELTA = "delta"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MESSAGE = "message"
    USAGE = "usage"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass(frozen=True)
class SessionSpec:
    """Continuity policy for an active VYRELON development session."""

    id: str
    project_root: str
    agent_id: str | None = None
    model_id: str | None = None
    checkpoint_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolSpec:
    """Explicit executable capability exposed to an agent."""

    id: str
    description: str
    side_effect: ToolSideEffect = ToolSideEffect.READ
    permissions: frozenset[str] = frozenset()
    input_schema: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolRequest:
    """Normalized request to invoke a VYRELON tool."""

    tool_id: str
    arguments: dict[str, object] = field(default_factory=dict)
    session_id: str | None = None
    work_unit_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Normalized result returned by a VYRELON tool."""

    tool_id: str
    ok: bool
    output: object = None
    error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeEvent:
    """Normalized event emitted by an AI, tool, or execution runtime."""

    kind: RuntimeEventKind
    session_id: str | None = None
    work_unit_id: str | None = None
    payload: object = None
    sequence: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class ProtocolAdapter(Protocol):
    """Translate between provider wire formats and VYRELON requests/events."""

    def encode_request(self, request: object) -> object:
        ...

    def decode_event(self, payload: object) -> RuntimeEvent:
        ...


@dataclass(frozen=True)
class FallbackPolicy:
    """Ordered model/provider fallback behavior."""

    model_ids: tuple[str, ...] = ()
    max_attempts: int | None = None
    retryable_errors: frozenset[str] = frozenset()
    metadata: dict[str, object] = field(default_factory=dict)

    def candidates(self) -> tuple[str, ...]:
        if self.max_attempts is None:
            return self.model_ids
        return self.model_ids[: max(self.max_attempts, 0)]
