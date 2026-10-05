"""Recovery identity regression tests for durable tool calling."""

from __future__ import annotations

from core.contracts.ai import ModelSpec
from core.contracts.agent_execution_runtime import (
    RuntimeEventKind,
    ToolRequest,
    ToolSideEffect,
    ToolSpec,
)
from core.contracts.execution_cursor import ExecutionCursor
from core.contracts.model_runtime import ModelResponse
from core.contracts.replay import ReplayDisposition, ReplayPolicy
from core.contracts.tool_ledger import ToolInvocationRecord, ToolInvocationState
from core.execution_state import ExecutionStateStore
from core.tool_ledger import ToolInvocationStore
from runtime.policy import ExecutionPolicy
from runtime.tool_calling import ToolCallingRuntime, ToolRuntime


class _ResumeAdapter:
    def generate_with_tools(self, model, request, tools):
        return ModelResponse(
            text="resumed",
            model_id=model.id,
            metadata={"tool_calls": ()},
        )


def test_resume_preserves_decision_agent_model_identity_and_idempotency(
    tmp_path,
) -> None:
    work_unit_id = "work-recovery"
    decision_id = "decision-1"
    agent_id = "agent-developer"
    model_id = "model-test"
    invocation_id = "inv-1"
    call_id = "call-1"
    idempotency_key = "idem-1"

    cursor_store = ExecutionStateStore(tmp_path / "execution")
    ledger_store = ToolInvocationStore(tmp_path / "ledger")
    events = []
    observed_request: list[ToolRequest] = []

    tool_runtime = ToolRuntime(ExecutionPolicy())

    def handler(request: ToolRequest) -> object:
        observed_request.append(request)
        return "ok"

    tool_runtime.register(
        ToolSpec(
            id="filesystem.read",
            description="read a file",
            side_effect=ToolSideEffect.READ,
        ),
        handler,
    )

    cursor_store.append_message(
        work_unit_id,
        role="assistant",
        round_number=1,
        content="read it",
        metadata={
            "model_id": model_id,
            "response": {
                "model_id": model_id,
                "tool_calls": [
                    {
                        "call_id": call_id,
                        "tool_id": "filesystem.read",
                        "arguments": {"path": "example.txt"},
                    }
                ],
            },
        },
    )
    cursor_store.save_cursor(
        ExecutionCursor(
            work_unit_id=work_unit_id,
            event_sequence=2,
            round_number=1,
            agent_id=agent_id,
            model_id=model_id,
            conversation_revision=1,
            next_tool_call_id=call_id,
        )
    )
    ledger_store.append(
        ToolInvocationRecord(
            invocation_id=invocation_id,
            work_unit_id=work_unit_id,
            tool_id="filesystem.read",
            arguments={"path": "example.txt"},
            state=ToolInvocationState.STARTED,
            replay_policy=ReplayPolicy(
                ReplayDisposition.SAFE,
                reason="read-only tool",
                idempotency_key=idempotency_key,
            ),
            sequence=1,
            call_id=call_id,
            idempotency_key=idempotency_key,
            decision_id=decision_id,
            agent_id=agent_id,
            model_id=model_id,
        )
    )

    runtime = ToolCallingRuntime(
        models={model_id: ModelSpec(id=model_id, provider_id="test")},
        adapters={model_id: _ResumeAdapter()},
        tools=tool_runtime,
        ledger_store=ledger_store,
        cursor_store=cursor_store,
        agent_id=agent_id,
        event_sink=events.append,
    )

    result = runtime.resume(
        __import__("core.contracts.model_runtime", fromlist=["ModelRequest"]).ModelRequest(
            prompt="resume",
            metadata={"execution_decision": {
                "decision_id": decision_id,
                "agent_id": agent_id,
                "model_id": model_id,
            }},
        ),
        model_id=model_id,
        work_unit_id=work_unit_id,
    )

    assert result.model_id == model_id
    assert len(observed_request) == 1
    assert observed_request[0].metadata["invocation_id"] == invocation_id
    assert observed_request[0].metadata["idempotency_key"] == idempotency_key
    assert observed_request[0].metadata["decision_id"] == decision_id
    assert observed_request[0].metadata["agent_id"] == agent_id
    assert observed_request[0].metadata["model_id"] == model_id

    record = ledger_store.load(work_unit_id)[-1]
    assert record.state is ToolInvocationState.COMPLETED
    assert record.invocation_id == invocation_id
    assert record.idempotency_key == idempotency_key
    assert record.decision_id == decision_id
    assert record.agent_id == agent_id
    assert record.model_id == model_id

    replay_events = [
        event for event in events
        if event.kind in {RuntimeEventKind.TOOL_CALL, RuntimeEventKind.TOOL_RESULT}
    ]
    assert [event.kind for event in replay_events] == [
        RuntimeEventKind.TOOL_CALL,
        RuntimeEventKind.TOOL_RESULT,
    ]
    for event in replay_events:
        assert event.payload["invocation_id"] == invocation_id
        assert event.payload["idempotency_key"] == idempotency_key
        assert event.payload["decision_id"] == decision_id
        assert event.payload["agent_id"] == agent_id
        assert event.payload["model_id"] == model_id
