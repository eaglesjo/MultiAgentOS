import tempfile
import unittest
from pathlib import Path

from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind
from core.contracts.recovery import RecoveryDisposition
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.agent_execution_runtime import AgentExecutionRuntime


class RuntimeRecoveryContractTests(unittest.TestCase):
    def test_in_flight_tool_requires_review(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = AgentExecutionRuntime()
            root = Path(temp)
            runtime.state_store(root).save(WorkUnit("w1", "resume", WorkStatus.EXECUTING))
            runtime.event_store(root).append(RuntimeEvent(
                kind=RuntimeEventKind.TOOL_CALL,
                work_unit_id="w1",
                payload={"call_id": "c1", "tool_id": "filesystem.write"},
            ))

            plan = runtime.recovery_plan(root, "w1")

            self.assertEqual(plan.disposition, RecoveryDisposition.REVIEW_REQUIRED)
            self.assertFalse(plan.safe_to_resume)
            self.assertEqual(plan.pending_tool_call_ids, ("c1",))
            self.assertTrue(plan.requires_human_review)

    def test_failed_work_without_pending_tool_can_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = AgentExecutionRuntime()
            root = Path(temp)
            runtime.state_store(root).save(WorkUnit("w2", "resume", WorkStatus.FAILED))

            plan = runtime.recovery_plan(root, "w2")

            self.assertEqual(plan.disposition, RecoveryDisposition.RESUME)
            self.assertTrue(plan.safe_to_resume)

    def test_completed_work_is_terminal(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = AgentExecutionRuntime()
            root = Path(temp)
            runtime.state_store(root).save(WorkUnit("w3", "resume", WorkStatus.COMPLETED))
            runtime.event_store(root).append(RuntimeEvent(
                kind=RuntimeEventKind.COMPLETED,
                work_unit_id="w3",
                payload={"rounds": 1},
            ))

            plan = runtime.recovery_plan(root, "w3")

            self.assertEqual(plan.disposition, RecoveryDisposition.COMPLETED)
            self.assertFalse(plan.safe_to_resume)


if __name__ == "__main__":
    unittest.main()
