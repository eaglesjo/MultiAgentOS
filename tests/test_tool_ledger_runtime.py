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
from runtime.tool_calling import ToolCallingRuntime, ToolExecutionError, ToolRuntime


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

    def test_ledger_rejects_work_unit_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "tool-ledger"
            store = ToolInvocationStore(root)
            from core.contracts.replay import ReplayDisposition, ReplayPolicy
            from core.contracts.tool_ledger import ToolInvocationRecord

            policy = ReplayPolicy(ReplayDisposition.SAFE, reason="read-only")
            for work_unit_id in ("../outside", r"..\\outside", "bad:stream"):
                with self.subTest(work_unit_id=work_unit_id):
                    with self.assertRaisesRegex(ValueError, "invalid tool ledger work_unit_id"):
                        store.append(ToolInvocationRecord(
                            "inv-escape", work_unit_id, "filesystem.read", {},
                            ToolInvocationState.REQUESTED, policy, 1,
                        ))
                    with self.assertRaisesRegex(ValueError, "invalid tool ledger work_unit_id"):
                        store.load(work_unit_id)
            self.assertFalse((Path(temp) / "outside.jsonl").exists())

    def test_ledger_rejects_symlink_escape_when_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "tool-ledger"
            root.mkdir()
            outside = Path(temp) / "outside.jsonl"
            outside.write_text("", encoding="utf-8")
            link = root / "work-1.jsonl"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable in this environment")
            store = ToolInvocationStore(root)
            with self.assertRaisesRegex(ValueError, "escapes configured root"):
                store.append(__import__("core.contracts.tool_ledger", fromlist=["ToolInvocationRecord"]).ToolInvocationRecord(
                    "inv-1", "work-1", "filesystem.read", {},
                    ToolInvocationState.REQUESTED,
                    __import__("core.contracts.replay", fromlist=["ReplayPolicy", "ReplayDisposition"]).ReplayPolicy(
                        __import__("core.contracts.replay", fromlist=["ReplayDisposition"]).ReplayDisposition.SAFE,
                        reason="read-only",
                    ),
                    1,
                ))
            self.assertEqual(outside.read_text(encoding="utf-8"), "")

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

    def test_cursor_resume_returns_persisted_final_response_without_new_model_call(self):
        class FailingAdapter:
            def generate_with_tools(self, model, request, tools):
                raise AssertionError("model must not be called for an already persisted final response")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = ExecutionStateStore(root / "execution-state")
            state.append_message(
                "work-1",
                role="request",
                round_number=1,
                content="inspect",
                metadata={"system": "system", "request": {}},
            )
            state.append_message(
                "work-1",
                role="assistant",
                round_number=1,
                content="already complete",
                metadata={"model_id": "model-a", "response": {"model_id": "model-a", "tool_calls": []}},
            )
            state.save_cursor(
                ExecutionCursor("work-1", 2, 1, "developer", "model-a", 2, None)
            )
            tools = ToolRuntime()
            runtime = ToolCallingRuntime(
                models={"model-a": ModelSpec("model-a", "provider-a", frozenset({"code"}))},
                adapters={"model-a": FailingAdapter()},
                tools=tools,
                cursor_store=state,
                agent_id="developer",
            )
            result = runtime.resume(
                ModelRequest(prompt="inspect", system="system", metadata={}),
                model_id="model-a",
                work_unit_id="work-1",
            )
            self.assertEqual(result.response.text, "already complete")
            self.assertEqual(result.rounds, 1)

    def test_cursor_resume_executes_pending_safe_tool_then_continues_model_round(self):
        class Adapter:
            def generate_with_tools(self, model, request, tools):
                return ModelResponse(text="resumed-final", model_id=model.id)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = ToolInvocationStore(root / "tool-ledger")
            state = ExecutionStateStore(root / "execution-state")
            tools = ToolRuntime()
            tools.register(
                ToolSpec("filesystem.read", "read a file", ToolSideEffect.READ),
                lambda request: "resumed content",
            )
            from core.contracts.replay import ReplayDisposition, ReplayPolicy
            from core.contracts.tool_ledger import ToolInvocationRecord

            ledger.append(ToolInvocationRecord(
                invocation_id="inv-1",
                work_unit_id="work-1",
                tool_id="filesystem.read",
                arguments={"path": "README.md"},
                state=ToolInvocationState.STARTED,
                replay_policy=ReplayPolicy(ReplayDisposition.SAFE, reason="read-only"),
                sequence=1,
                call_id="read-1",
                idempotency_key="inv-1",
            ))
            state.append_message(
                "work-1",
                role="request",
                round_number=1,
                content="inspect",
                metadata={"system": "system", "request": {}},
            )
            state.append_message(
                "work-1",
                role="assistant",
                round_number=1,
                content="",
                metadata={
                    "model_id": "model-a",
                    "response": {
                        "tool_calls": [
                            {"id": "read-1", "name": "filesystem.read", "arguments": {"path": "README.md"}}
                        ]
                    },
                },
            )
            state.save_cursor(
                ExecutionCursor(
                    "work-1", 2, 1, "developer", "model-a", 2, "read-1"
                )
            )
            runtime = ToolCallingRuntime(
                models={"model-a": ModelSpec("model-a", "provider-a", frozenset({"code"}))},
                adapters={"model-a": Adapter()},
                tools=tools,
                ledger_store=ledger,
                cursor_store=state,
                agent_id="developer",
            )
            result = runtime.resume(
                ModelRequest(prompt="inspect", system="system", metadata={}),
                model_id="model-a",
                work_unit_id="work-1",
            )
            cursor = state.load_cursor("work-1")
            self.assertEqual(result.response.text, "resumed-final")
            self.assertEqual(cursor.round_number, 2)
            self.assertIsNone(cursor.next_tool_call_id)
            self.assertGreater(cursor.event_sequence, 2)
            self.assertEqual(ledger.load("work-1")[0].state, ToolInvocationState.COMPLETED)

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



    def test_execution_decision_identity_is_persisted_in_ledger_and_events(self):
        class Adapter:
            def generate_with_tools(self, model, request, tools):
                if request.metadata.get("tool_history"):
                    return ModelResponse(text="done", model_id=model.id)
                return ModelResponse(
                    text="",
                    model_id=model.id,
                    metadata={
                        "tool_calls": [
                            {
                                "id": "read-1",
                                "name": "filesystem.read",
                                "arguments": {"path": "README.md"},
                            }
                        ]
                    },
                )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = ToolInvocationStore(root / "tool-ledger")
            from core.state import RuntimeEventStore

            events = RuntimeEventStore(root / "events")
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
                event_sink=events.append,
                agent_id="agent-a",
            )
            runtime.execute(
                ModelRequest(
                    prompt="inspect",
                    metadata={
                        "execution_decision": {
                            "decision_id": "decision-123",
                            "agent_id": "agent-a",
                            "model_id": "model-a",
                        }
                    },
                ),
                model_id="model-a",
                work_unit_id="work-1",
            )

            records = ledger.load("work-1")
            assert len(records) == 1
            assert records[0].decision_id == "decision-123"
            assert records[0].agent_id == "agent-a"
            assert records[0].model_id == "model-a"

            stored_events = events.load("work-1")
            tool_call = next(
                event for event in stored_events
                if event["kind"] == "tool_call"
            )
            tool_result = next(
                event for event in stored_events
                if event["kind"] == "tool_result"
            )
            assert tool_call["payload"]["decision_id"] == "decision-123"
            assert tool_call["payload"]["agent_id"] == "agent-a"
            assert tool_call["payload"]["model_id"] == "model-a"
            assert tool_result["payload"]["decision_id"] == "decision-123"

    def test_store_finds_invocations_by_idempotency_key(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ToolInvocationStore(Path(temp) / "tool-ledger")
            from core.contracts.replay import ReplayDisposition, ReplayPolicy
            from core.contracts.tool_ledger import ToolInvocationRecord
            policy = ReplayPolicy(ReplayDisposition.SAFE, reason="read-only")
            store.append(ToolInvocationRecord(
                "inv-1", "work-1", "filesystem.read", {},
                ToolInvocationState.COMPLETED, policy, 1, idempotency_key="idem-1",
            ))
            self.assertEqual(
                tuple(item.invocation_id for item in store.find_by_idempotency_key("work-1", "idem-1")),
                ("inv-1",),
            )
            self.assertEqual(store.find_by_idempotency_key("work-1", "missing"), ())

    def test_tool_calling_rejects_reuse_of_completed_idempotency_key(self):
        class Adapter:
            def __init__(self):
                self.calls = 0

            def generate_with_tools(self, model, request, tools):
                self.calls += 1
                if self.calls == 1:
                    return ModelResponse(
                        text="", model_id=model.id,
                        metadata={"tool_calls": [{
                            "id": "write-1", "name": "external.write",
                            "arguments": {"value": 1}, "idempotency_key": "idem-1",
                        }]},
                    )
                return ModelResponse(text="done", model_id=model.id)
        with tempfile.TemporaryDirectory() as temp:
            store = ToolInvocationStore(Path(temp) / "tool-ledger")
            executions = []
            tools = ToolRuntime()
            tools.register(
                ToolSpec("external.write", "write a value", ToolSideEffect.WRITE),
                lambda request: executions.append(request) or "mutated",
            )
            runtime = ToolCallingRuntime(
                models={"model-a": ModelSpec("model-a", "provider-a", frozenset({"code"}))},
                adapters={"model-a": Adapter()}, tools=tools, ledger_store=store,
            )
            runtime.execute(ModelRequest(prompt="write", metadata={}), model_id="model-a", work_unit_id="work-1")
            # Use a fresh adapter for the second top-level execution so the
            # duplicate key reaches the runtime's idempotency guard.
            runtime.adapters["model-a"] = Adapter()
            with self.assertRaisesRegex(ToolExecutionError, "idempotency key already used"):
                runtime.execute(ModelRequest(prompt="retry", metadata={}), model_id="model-a", work_unit_id="work-1")
            self.assertEqual(len(executions), 1)
            self.assertEqual(store.load("work-1")[0].state, ToolInvocationState.COMPLETED)

    def test_tool_calling_rejects_reuse_of_unresolved_idempotency_key_before_handler(self):
        class Adapter:
            def generate_with_tools(self, model, request, tools):
                return ModelResponse(
                    text="", model_id=model.id,
                    metadata={"tool_calls": [{
                        "id": "write-1", "name": "external.write",
                        "arguments": {"value": 1}, "idempotency_key": "idem-1",
                    }]},
                )
        with tempfile.TemporaryDirectory() as temp:
            from core.contracts.replay import ReplayDisposition, ReplayPolicy
            from core.contracts.tool_ledger import ToolInvocationRecord
            store = ToolInvocationStore(Path(temp) / "tool-ledger")
            store.append(ToolInvocationRecord(
                "inv-existing", "work-1", "external.write", {"value": 1},
                ToolInvocationState.STARTED,
                ReplayPolicy(ReplayDisposition.REVIEW_REQUIRED, reason="unknown side effect"),
                1, call_id="write-0", idempotency_key="idem-1",
            ))
            executions = []
            tools = ToolRuntime()
            tools.register(
                ToolSpec("external.write", "write a value", ToolSideEffect.WRITE),
                lambda request: executions.append(request) or "mutated",
            )
            runtime = ToolCallingRuntime(
                models={"model-a": ModelSpec("model-a", "provider-a", frozenset({"code"}))},
                adapters={"model-a": Adapter()}, tools=tools, ledger_store=store,
            )
            with self.assertRaisesRegex(ToolExecutionError, "idempotency key already used"):
                runtime.execute(ModelRequest(prompt="retry", metadata={}), model_id="model-a", work_unit_id="work-1")
            self.assertEqual(executions, [])


if __name__ == "__main__":
    unittest.main()
