"""Recovery replay-policy regression tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.contracts.ai import ModelSpec
from core.contracts.agent_execution_runtime import ToolSideEffect, ToolSpec
from core.contracts.execution_cursor import ExecutionCursor
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.replay import ReplayDisposition, ReplayPolicy
from core.contracts.tool_ledger import ToolInvocationRecord, ToolInvocationState
from core.execution_state import ExecutionStateStore
from core.tool_ledger import ToolInvocationStore
from runtime.policy import ExecutionPolicy
from runtime.tool_calling import ToolCallingRuntime, ToolExecutionError, ToolRuntime


class _NoToolAdapter:
    def generate_with_tools(self, model, request, tools):
        return ModelResponse(text="done", model_id=model.id, metadata={"tool_calls": ()})


class RecoveryReplayPolicyTests(unittest.TestCase):
    def _build_runtime(self, root: Path, disposition: ReplayDisposition):
        work_unit_id = "work-replay-policy"
        model_id = "model-test"
        call_id = "call-1"
        cursor_store = ExecutionStateStore(root / "execution")
        ledger_store = ToolInvocationStore(root / "ledger")
        runtime = ToolRuntime(ExecutionPolicy())
        executions = []

        runtime.register(
            ToolSpec(id="external.write", description="side effect", side_effect=ToolSideEffect.WRITE),
            lambda request: executions.append(request) or "mutated",
        )
        cursor_store.append_message(
            work_unit_id,
            role="assistant",
            round_number=1,
            content="write it",
            metadata={
                "response": {
                    "model_id": model_id,
                    "tool_calls": [{"call_id": call_id, "tool_id": "external.write", "arguments": {"value": 1}}],
                }
            },
        )
        cursor_store.save_cursor(
            ExecutionCursor(
                work_unit_id=work_unit_id,
                event_sequence=2,
                round_number=1,
                agent_id="agent-1",
                model_id=model_id,
                conversation_revision=1,
                next_tool_call_id=call_id,
            )
        )
        ledger_store.append(
            ToolInvocationRecord(
                invocation_id="inv-1",
                work_unit_id=work_unit_id,
                tool_id="external.write",
                arguments={"value": 1},
                state=ToolInvocationState.STARTED,
                replay_policy=ReplayPolicy(disposition, reason="test"),
                sequence=1,
                call_id=call_id,
                idempotency_key="idem-1",
                decision_id="decision-1",
                agent_id="agent-1",
                model_id=model_id,
            )
        )
        tool_runtime = ToolCallingRuntime(
            models={model_id: ModelSpec(id=model_id, provider_id="test")},
            adapters={model_id: _NoToolAdapter()},
            tools=runtime,
            ledger_store=ledger_store,
            cursor_store=cursor_store,
            agent_id="agent-1",
        )
        return tool_runtime, executions, model_id, work_unit_id

    def test_recovery_enforces_review_and_never_policy(self):
        cases = [
            (ReplayDisposition.REVIEW_REQUIRED, False, "human recovery approval required"),
            (ReplayDisposition.NEVER, True, "cannot be replayed"),
        ]
        for disposition, approved, expected in cases:
            with self.subTest(disposition=disposition, approved=approved):
                with tempfile.TemporaryDirectory() as tmp:
                    runtime, executions, model_id, work_unit_id = self._build_runtime(Path(tmp), disposition)
                    with self.assertRaisesRegex(ToolExecutionError, expected):
                        runtime.resume(
                            ModelRequest(prompt="resume"),
                            model_id=model_id,
                            work_unit_id=work_unit_id,
                            approved=approved,
                        )
                    self.assertEqual(executions, [])

    def test_recovery_reviewed_side_effect_can_resume_with_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, executions, model_id, work_unit_id = self._build_runtime(
                Path(tmp), ReplayDisposition.REVIEW_REQUIRED
            )
            runtime.resume(
                ModelRequest(prompt="resume"),
                model_id=model_id,
                work_unit_id=work_unit_id,
                approved=True,
            )
            self.assertEqual(len(executions), 1)
            self.assertEqual(executions[0].metadata["invocation_id"], "inv-1")
            self.assertEqual(executions[0].metadata["idempotency_key"], "idem-1")


if __name__ == "__main__":
    unittest.main()
