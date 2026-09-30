"""Provider-neutral streaming and reasoning contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class StreamEventKind(StrEnum):
    TEXT_DELTA = "text_delta"
    REASONING_DELTA = "reasoning_delta"
    TOOL_CALL_DELTA = "tool_call_delta"
    COMPLETED = "completed"
    ERROR = "error"


class StreamCheckpointStatus(StrEnum):
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class StreamEvent:
    """Normalized incremental model output event."""

    kind: StreamEventKind
    sequence: int
    text: str = ""
    call_id: str | None = None
    tool_id: str | None = None
    arguments_delta: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StreamCheckpoint:
    """Explicit durable boundary for one assembled model stream."""

    checkpoint_id: str
    work_unit_id: str
    status: StreamCheckpointStatus
    sequence: int
    model_id: str
    round_number: int
    text: str = ""
    reasoning: str = ""
    tool_calls: tuple[dict[str, object], ...] = ()
    cursor_sequence: int | None = None
    conversation_revision: int | None = None


@dataclass(frozen=True)
class StreamResult:
    """Final assembled model output from one stream."""

    text: str
    reasoning: str
    tool_calls: tuple[dict[str, object], ...] = ()
    events: tuple[StreamEvent, ...] = ()
