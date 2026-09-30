import tempfile
import unittest
from pathlib import Path

from core.contracts.agent_execution_runtime import ToolSideEffect, ToolSpec
from core.contracts.ai import ModelSpec
from core.contracts.model_runtime import ModelRequest, ModelResponse
from core.contracts.tool_ledger import ToolInvocationState
from core.contracts.work_unit import WorkUnit, WorkStatus
from core.contracts.recovery import RecoveryDisposition
from core.tool_ledger import ToolInvocationStore
from core.execution_state import ExecutionStateStore
from core.contracts.execution_cursor import ExecutionCursor
from runtime.tool_calling import ToolCallingRuntime, ToolRuntime


class DurableToolLedgerRuntimeTests(unittest.TestCase):
    def test_store_keeps_latest_state_for_each_invocation(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ToolInvocationStore(Path(temp) / "tool-ledger")
            from core.contracts.replay import ReplayDisposition, ReplayPolicy
            from core.contracts.tool_ledger import ToolInvocationRecord

            policy = ReplayPolicy(ReplayDisposition.SAFE, reason="read-only")
            store.append(ToolInvocationRecord("inv-1", "work-1", "filesystem.read", {}, ToolInvocationState.REQUESTED, policy, 1))
            store.append(ToolInvocationRecord("inv-1", "work-1", "filesystem.read", {}, ToolInvocationState.STARTED, policy, 2))
            store.append(ToolInvocationRecord("inv-1", "work-1", "filesystem.read", {}, ToolInvocationState.COMPLETED, policy, 3, result_reference="inv-1"))
            records = store.load("work-1")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].state, ToolInvocationState.COMPLETED)
            self.assertFalse(store.has_unresolved("work-1"))

    def test_tool_calling_persists_requested_started_completed(self):
        class Adapter:
            def __init__(self):
                self.calls = 0

            def generate_with_tools(self, model, request, tools):
                self.calls += 1
                if self.calls == 1:
                    return ModelResponse(
                        text="",
                        model_id=model.id,
                        metadata={"tool_calls": [{"id": "read-1", "name": "filesystem.read", "arguments": {"path": "README.md"}}]},
                    )
                return ModelResponse(text="done", model_id=model.id)

        with tempfile.TemporaryDirectory() as temp:
            store = ToolInvocationStore(Path(temp) / "tool-ledger")
            tools = ToolRuntime()
            tools.register(
                ToolSpec("filesystem.read", "read a file", ToolSideEffect.READ),
                lambda request: "content",
            )
            runtime = ToolCallingRuntime(
                models={"model-a": ModelSpec("model-a", "provider-a", frozenset({"code"}))},
                adapters={"model-a": Adapter()},
                tools=tools,
                ledger_store=store,
            )
            result = runtime.execute(
                ModelRequest(prompt="inspect", metadata={}),
                model_id="model-a",
                work_unit_id="work-1",
            )
            records = store.load("work-1")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].state, ToolInvocationState.COMPLETED)
            self.assertEqual(records[0].tool_id, "filesystem.read")
            self.assertEqual(result.rounds, 2)
            self.assertFalse(store.has_unresolved("work-1"))

    def test_recovery_gate_allows_explicitly_safe_unresolved_invocation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = __import__("runtime", fromlist=["AgentExecutionRuntime"]).AgentExecutionRuntime()
            work = WorkUnit("work-1", "inspect")
            work.transition(WorkStatus.EXECUTING)
            runtime.state_store(root).save(work)
            from core.contracts.replay import ReplayDisposition, ReplayPolicy
            from core.contracts.tool_ledger import ToolInvocationRecord

            runtime.tool_ledger_store(root).append(ToolInvocationRecord(
                "inv-1", "work-1", "filesystem.read", {"path": "README.md"},
                ToolInvocationState.STARTED,
                ReplayPolicy(ReplayDisposition.SAFE, reason="read-only"),
                1,
            ))
            plan = runtime.recovery_plan(root, "work-1")
            self.assertEqual(plan.disposition, RecoveryDisposition.RESUME)
            self.assertTrue(plan.safe_to_resume)
            self.assertEqual(plan.pending_tool_call_ids, ("inv-1",))

    def test_execution_cursor_and_model_messages_are_durable(self):
        class Adapter:
            def __init__(self):
                self.calls = 0

            def generate_with_tools(self, model, request, tools):
                self.calls += 1
                if self.calls == 1:
                    return ModelResponse(
                        text="",
                        model_id=model.id,
                        metadata={"tool_calls": [{"id": "read-1", "name": "filesystem.read", "arguments": {"path": "README.md"}}]},
                    )
                return ModelResponse(text="done", model_id=model.id)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = ToolInvocationStore(root / "tool-ledger")
            state = ExecutionStateStore(root / "execution-state")
            tools = ToolRuntime()
            tools.register(
                ToolSpec("filesystem.read", "read a file", ToolSideEffect.READ),
                lambda request: "content",
            )
            runtime = ToolCallingRuntime(
                models={"model-a": ModelSpec("model-a", "provider-a", frozenset({"code"}))},
                adapters={"model-a": Adapter()},
                tools=tools,
                ledger_store=ledger,
                cursor_store=state,
                agent_id="developer",
            )
            runtime.execute(
                ModelRequest(prompt="inspect", system="system", metadata={"work_unit_id": "work-1"}),
                model_id="model-a",
                work_unit_id="work-1",
            )
            cursor = state.load_cursor("work-1")
            messages = state.load_messages("work-1")
            self.assertEqual(cursor.work_unit_id, "work-1")
            self.assertEqual(cursor.agent_id, "developer")
            self.assertEqual(cursor.round_number, 2)
            self.assertIsNone(cursor.next_tool_call_id)
            self.assertEqual(cursor.conversation_revision, len(messages))
            self.assertEqual([item["role"] for item in messages], ["request", "assistant", "tool", "request", "assistant"])
            self.assertEqual([item["revision"] for item in messages], [1, 2, 3, 4, 5])

    def test_execution_cursor_advances_monotonically(self):
        with tempfile.TemporaryDirectory() as temp:
            state = ExecutionStateStore(Path(temp) / "execution-state")
            previous = ExecutionCursor("work-1", 1, 1, "developer", "model-a")
            current = ExecutionCursor("work-1", 2, 1, "developer", "model-a", 1)
            state.save_cursor(previous)
            state.save_cursor(current)
            loaded = state.load_cursor("work-1")
            self.assertTrue(loaded.advances_from(previous))
            self.assertEqual(loaded.event_sequence, 2)

    def test_started_invocation_is_unresolved_after_runtime_crash_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ToolInvocationStore(Path(temp) / "tool-ledger")
            from core.contracts.replay import ReplayDisposition, ReplayPolicy
            from core.contracts.tool_ledger import ToolInvocationRecord

            store.append(ToolInvocationRecord(
                "inv-1", "work-1", "shell.run", {"command": "touch x"},
                ToolInvocationState.STARTED,
                ReplayPolicy(ReplayDisposition.REVIEW_REQUIRED, reason="side effect may have occurred"),
                1,
            ))
            unresolved = store.unresolved("work-1")
            self.assertEqual(tuple(item.invocation_id for item in unresolved), ("inv-1",))
            self.assertTrue(unresolved[0].requires_recovery_review)


if __name__ == "__main__":
    unittest.main()
