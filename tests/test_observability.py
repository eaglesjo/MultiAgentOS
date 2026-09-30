import tempfile
import unittest
from pathlib import Path

from core.contracts.work_unit import WorkUnit, WorkStatus
from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind
from core.state import RuntimeEventStore, WorkStateStore
from runtime.observability import ExecutionObservability


class ExecutionObservabilityTests(unittest.TestCase):
    def test_completed_work_unit_summary_is_bounded_and_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = WorkUnit(id="wu-obs", objective="inspect", status=WorkStatus.COMPLETED)
            WorkStateStore(root / ".multiagentos" / "work").save(work)
            RuntimeEventStore(root / ".multiagentos" / "events").append(RuntimeEvent(
                kind=RuntimeEventKind.REQUEST,
                session_id="session",
                work_unit_id=work.id,
                payload={"objective": "inspect", "api_key": "secret"},
            ))
            RuntimeEventStore(root / ".multiagentos" / "events").append(RuntimeEvent(
                kind=RuntimeEventKind.COMPLETED,
                session_id="session",
                work_unit_id=work.id,
                payload={"rounds": 1},
            ))

            summary = ExecutionObservability(root).summarize(work.id, timeline_limit=1)
            self.assertEqual(summary.execution_state, "completed")
            self.assertEqual(summary.event_count, 2)
            self.assertEqual(summary.timeline, ({"sequence": 2, "kind": "completed"},))
            self.assertNotIn("secret", str(summary))
            self.assertEqual(
                ExecutionObservability(root).as_dict(work.id)["unresolved_tool_count"], 0
            )

    def test_interrupted_stream_is_reported_without_being_completed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = WorkUnit(id="wu-interrupted", objective="stream")
            WorkStateStore(root / ".multiagentos" / "work").save(work)
            RuntimeEventStore(root / ".multiagentos" / "events").append(RuntimeEvent(
                kind=RuntimeEventKind.ERROR,
                session_id="session",
                work_unit_id=work.id,
                payload={"stream": "interrupted"},
            ))
            summary = ExecutionObservability(root).summarize(work.id)
            self.assertEqual(summary.execution_state, "executing")
            self.assertNotEqual(summary.execution_state, "completed")


if __name__ == "__main__":
    unittest.main()
