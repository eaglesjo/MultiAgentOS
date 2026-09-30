"""Provider-neutral streaming runtime boundary."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from uuid import uuid4

from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind
from core.contracts.execution_cursor import ExecutionCursor
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.streaming import (
    StreamCheckpoint,
    StreamCheckpointStatus,
    StreamEvent,
    StreamEventKind,
    StreamResult,
)
from core.execution_state import ExecutionStateStore
from core.security import redact_sensitive


@dataclass(frozen=True)
class StreamingExecution:
    response: ModelResponse
    result: StreamResult
    checkpoint: StreamCheckpoint | None = None


class StreamingRuntime:
    """Normalize transient stream events and persist only explicit safe boundaries."""

    def __init__(
        self,
        *,
        event_sink: Callable[[RuntimeEvent], None] | None = None,
        observation_sink: Callable[[StreamEvent], None] | None = None,
        execution_state_store: ExecutionStateStore | None = None,
    ) -> None:
        self.event_sink = event_sink
        self.observation_sink = observation_sink
        self.execution_state_store = execution_state_store

    def consume(
        self,
        events: Iterable[StreamEvent],
        *,
        model_id: str,
        request: ModelRequest,
        session_id: str | None = None,
        work_unit_id: str | None = None,
        round_number: int = 1,
        agent_id: str = "streaming",
    ) -> StreamingExecution:
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        calls: dict[str, dict[str, object]] = {}
        normalized: list[StreamEvent] = []
        expected = 1
        completed = False

        try:
            for event in events:
                if event.sequence != expected:
                    raise ValueError(
                        f"stream sequence gap: expected {expected}, got {event.sequence}"
                    )
                expected += 1
                safe = self._redact_event(event)
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

                if self.observation_sink is not None:
                    self.observation_sink(safe)
        except Exception as exc:
            self._persist_interruption(
                model_id=model_id,
                work_unit_id=work_unit_id,
                round_number=round_number,
                sequence=max(expected - 1, 0),
                text="".join(text_parts),
                reasoning="".join(reasoning_parts),
            )
            if self.event_sink is not None:
                self.event_sink(RuntimeEvent(
                    kind=RuntimeEventKind.ERROR,
                    session_id=session_id,
                    work_unit_id=work_unit_id,
                    payload={
                        "stream": "interrupted",
                        "sequence": max(expected - 1, 0),
                        "error": str(redact_sensitive(str(exc))),
                    },
                ))
            raise

        if not completed:
            self._persist_interruption(
                model_id=model_id,
                work_unit_id=work_unit_id,
                round_number=round_number,
                sequence=max(expected - 1, 0),
                text="".join(text_parts),
                reasoning="".join(reasoning_parts),
            )
            raise RuntimeError("stream ended without completion event")

        tool_calls = self._assemble_tool_calls(calls)
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
        checkpoint = self._persist_completion(
            response=response,
            result=result,
            model_id=model_id,
            work_unit_id=work_unit_id,
            round_number=round_number,
            sequence=expected - 1,
            agent_id=agent_id,
        )
        if self.event_sink is not None:
            self.event_sink(RuntimeEvent(
                kind=RuntimeEventKind.COMPLETED,
                session_id=session_id,
                work_unit_id=work_unit_id,
                payload={
                    "stream": "checkpointed",
                    "checkpoint_id": checkpoint.checkpoint_id if checkpoint else None,
                    "sequence": expected - 1,
                },
            ))
        return StreamingExecution(response, result, checkpoint)

    def resume(
        self,
        work_unit_id: str,
        *,
        model_id: str | None = None,
    ) -> StreamingExecution:
        """Reconstruct a completed stream from durable state without provider replay."""

        if self.execution_state_store is None:
            raise RuntimeError("execution state store is required for streaming resume")
        checkpoint = self.execution_state_store.load_stream_checkpoint(work_unit_id)
        if checkpoint.status is not StreamCheckpointStatus.COMPLETED:
            raise RuntimeError(
                "stream checkpoint is interrupted; provider execution requires a fresh run"
            )
        response = ModelResponse(
            text=checkpoint.text,
            model_id=model_id or checkpoint.model_id,
            metadata={
                "reasoning": checkpoint.reasoning,
                "tool_calls": checkpoint.tool_calls,
                "resumed_from_checkpoint": checkpoint.checkpoint_id,
            },
        )
        result = StreamResult(
            text=checkpoint.text,
            reasoning=checkpoint.reasoning,
            tool_calls=checkpoint.tool_calls,
            events=(),
        )
        return StreamingExecution(response, result, checkpoint)

    @staticmethod
    def _redact_event(event: StreamEvent) -> StreamEvent:
        return StreamEvent(
            kind=event.kind,
            sequence=event.sequence,
            text=str(redact_sensitive(event.text)),
            call_id=event.call_id,
            tool_id=event.tool_id,
            arguments_delta=str(redact_sensitive(event.arguments_delta)),
            metadata=redact_sensitive(dict(event.metadata)),
        )

    @staticmethod
    def _assemble_tool_calls(
        calls: dict[str, dict[str, object]],
    ) -> list[dict[str, object]]:
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
        return tool_calls

    def _persist_interruption(
        self,
        *,
        model_id: str,
        work_unit_id: str | None,
        round_number: int,
        sequence: int,
        text: str,
        reasoning: str,
    ) -> None:
        if self.execution_state_store is None or work_unit_id is None:
            return
        self.execution_state_store.save_stream_checkpoint(StreamCheckpoint(
            checkpoint_id=f"stream-{uuid4().hex}",
            work_unit_id=work_unit_id,
            status=StreamCheckpointStatus.INTERRUPTED,
            sequence=sequence,
            model_id=model_id,
            round_number=round_number,
            text=str(redact_sensitive(text)),
            reasoning=str(redact_sensitive(reasoning)),
        ))

    def _persist_completion(
        self,
        *,
        response: ModelResponse,
        result: StreamResult,
        model_id: str,
        work_unit_id: str | None,
        round_number: int,
        sequence: int,
        agent_id: str,
    ) -> StreamCheckpoint | None:
        if self.execution_state_store is None or work_unit_id is None:
            return None

        checkpoint_id = f"stream-{uuid4().hex}"
        existing_cursor_sequence = 0
        try:
            previous = self.execution_state_store.load_cursor(work_unit_id)
            existing_cursor_sequence = previous.event_sequence
        except FileNotFoundError:
            previous = None

        revision = self.execution_state_store.append_message(
            work_unit_id,
            role="assistant",
            round_number=round_number,
            content=response.text,
            metadata={
                "stream_checkpoint_id": checkpoint_id,
                "model_id": model_id,
                "reasoning": result.reasoning,
                "response": response.metadata,
            },
        )
        cursor_sequence = max(existing_cursor_sequence, sequence) + 1
        self.execution_state_store.save_cursor(ExecutionCursor(
            work_unit_id=work_unit_id,
            event_sequence=cursor_sequence,
            round_number=round_number,
            agent_id=agent_id,
            model_id=model_id,
            conversation_revision=revision,
            next_tool_call_id=(
                result.tool_calls[0]["call_id"]
                if result.tool_calls
                else None
            ),
        ))
        checkpoint = StreamCheckpoint(
            checkpoint_id=checkpoint_id,
            work_unit_id=work_unit_id,
            status=StreamCheckpointStatus.COMPLETED,
            sequence=sequence,
            model_id=model_id,
            round_number=round_number,
            text=result.text,
            reasoning=result.reasoning,
            tool_calls=result.tool_calls,
            cursor_sequence=cursor_sequence,
            conversation_revision=revision,
        )
        self.execution_state_store.save_stream_checkpoint(checkpoint)
        return checkpoint
