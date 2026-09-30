"""Provider-neutral streaming runtime boundary."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.streaming import StreamEvent, StreamEventKind, StreamResult
from core.security import redact_sensitive


@dataclass(frozen=True)
class StreamingExecution:
    response: ModelResponse
    result: StreamResult


class StreamingRuntime:
    """Normalize provider stream events without persisting transient deltas."""

    def __init__(self, *, event_sink=None) -> None:
        self.event_sink = event_sink

    def consume(
        self,
        events: Iterable[StreamEvent],
        *,
        model_id: str,
        request: ModelRequest,
        session_id: str | None = None,
        work_unit_id: str | None = None,
    ) -> StreamingExecution:
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        calls: dict[str, dict[str, object]] = {}
        normalized: list[StreamEvent] = []
        expected = 1
        completed = False

        for event in events:
            if event.sequence != expected:
                raise ValueError(
                    f"stream sequence gap: expected {expected}, got {event.sequence}"
                )
            expected += 1
            safe = StreamEvent(
                kind=event.kind,
                sequence=event.sequence,
                text=str(redact_sensitive(event.text)),
                call_id=event.call_id,
                tool_id=event.tool_id,
                arguments_delta=str(redact_sensitive(event.arguments_delta)),
                metadata=redact_sensitive(dict(event.metadata)),
            )
            normalized.append(safe)

            if safe.kind == StreamEventKind.TEXT_DELTA:
                text_parts.append(safe.text)
            elif safe.kind == StreamEventKind.REASONING_DELTA:
                reasoning_parts.append(safe.text)
            elif safe.kind == StreamEventKind.TOOL_CALL_DELTA:
                if not safe.call_id or not safe.tool_id:
                    raise ValueError("tool call delta requires call_id and tool_id")
                call = calls.setdefault(
                    safe.call_id,
                    {
                        "call_id": safe.call_id,
                        "tool_id": safe.tool_id,
                        "arguments": "",
                    },
                )
                call["arguments"] = str(call["arguments"]) + safe.arguments_delta
            elif safe.kind == StreamEventKind.ERROR:
                raise RuntimeError(safe.text or "stream failed")
            elif safe.kind == StreamEventKind.COMPLETED:
                completed = True

            if self.event_sink is not None:
                self.event_sink(
                    RuntimeEvent(
                        kind={
                            StreamEventKind.TEXT_DELTA: RuntimeEventKind.DELTA,
                            StreamEventKind.REASONING_DELTA: RuntimeEventKind.REASONING,
                            StreamEventKind.TOOL_CALL_DELTA: RuntimeEventKind.TOOL_CALL,
                            StreamEventKind.COMPLETED: RuntimeEventKind.COMPLETED,
                            StreamEventKind.ERROR: RuntimeEventKind.ERROR,
                        }[safe.kind],
                        session_id=session_id,
                        work_unit_id=work_unit_id,
                        payload={
                            "sequence": safe.sequence,
                            "text": safe.text,
                            "reasoning": safe.kind == StreamEventKind.REASONING_DELTA,
                            "call_id": safe.call_id,
                            "tool_id": safe.tool_id,
                            "arguments_delta": safe.arguments_delta,
                        },
                    )
                )

        if not completed:
            raise RuntimeError("stream ended without completion event")

        tool_calls: list[dict[str, object]] = []
        for call in calls.values():
            payload = dict(call)
            try:
                payload["arguments"] = json.loads(str(payload["arguments"]) or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid streamed tool arguments: {payload['call_id']}"
                ) from exc
            tool_calls.append(payload)

        text = "".join(text_parts)
        reasoning = "".join(reasoning_parts)
        result = StreamResult(text, reasoning, tuple(tool_calls), tuple(normalized))
        response = ModelResponse(
            text=text,
            model_id=model_id,
            metadata={
                "reasoning": reasoning,
                "tool_calls": tuple(tool_calls),
                "stream_event_count": len(normalized),
            },
        )
        return StreamingExecution(response, result)
