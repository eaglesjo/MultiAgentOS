import tempfile
import unittest
from pathlib import Path

from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.agent_execution_runtime import AgentExecutionRuntime


class RuntimeExecutionInspectionTests(unittest.TestCase):
    def test_tool_call_is_durable_before_result(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = AgentExecutionRuntime()
            root = Path(temp)
            store = runtime.event_store(root)
            store.append(RuntimeEvent(
                kind=RuntimeEventKind.TOOL_CALL,
                work_unit_id="work-1",
                payload={"call_id": "call-1", "tool_id": "filesystem.read"},
            ))
            runtime.state_store(root).save(WorkUnit("work-1", "inspect", WorkStatus.EXECUTING))

            snapshot = runtime.inspect_work_unit(root, "work-1")

            self.assertEqual(snapshot["execution_state"], "tool_in_flight")
            self.assertEqual(snapshot["pending_tool_call_ids"], ("call-1",))
            self.assertEqual(snapshot["event_count"], 1)

    def test_completed_tool_call_is_not_pending(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = AgentExecutionRuntime()
            root = Path(temp)
            store = runtime.event_store(root)
            store.append(RuntimeEvent(
                kind=RuntimeEventKind.TOOL_CALL,
                work_unit_id="work-2",
                payload={"call_id": "call-1", "tool_id": "filesystem.read"},
            ))
            store.append(RuntimeEvent(
                kind=RuntimeEventKind.TOOL_RESULT,
                work_unit_id="work-2",
                payload={"call_id": "call-1", "tool_id": "filesystem.read", "ok": True},
            ))
            runtime.state_store(root).save(WorkUnit("work-2", "inspect", WorkStatus.EXECUTING))

            snapshot = runtime.inspect_work_unit(root, "work-2")

            self.assertEqual(snapshot["execution_state"], "executing")
            self.assertEqual(snapshot["pending_tool_call_ids"], ())

    def test_completed_event_reports_terminal_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = AgentExecutionRuntime()
            root = Path(temp)
            store = runtime.event_store(root)
            store.append(RuntimeEvent(
                kind=RuntimeEventKind.COMPLETED,
                work_unit_id="work-3",
                payload={"rounds": 1},
            ))
            runtime.state_store(root).save(WorkUnit("work-3", "inspect", WorkStatus.COMPLETED))

            snapshot = runtime.inspect_work_unit(root, "work-3")

            self.assertEqual(snapshot["execution_state"], "completed")
            self.assertEqual(snapshot["last_event_kind"], "completed")
            self.assertEqual(snapshot["last_sequence"], 1)


if __name__ == "__main__":
    unittest.main()
