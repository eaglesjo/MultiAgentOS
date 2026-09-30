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
class StreamResult:
    """Final assembled model output from one stream."""

    text: str
    reasoning: str
    tool_calls: tuple[dict[str, object], ...] = ()
    events: tuple[StreamEvent, ...] = ()
