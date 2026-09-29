import tempfile
import unittest
from pathlib import Path

from core.contracts.agent_execution_runtime import RuntimeEvent, RuntimeEventKind
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.agent_execution_runtime import AgentExecutionRuntime


class RuntimeRecoveryResumeGateTests(unittest.TestCase):
    def test_in_flight_tool_call_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = AgentExecutionRuntime()
            work = WorkUnit("work-review", "continue safely")
            work.transition(WorkStatus.EXECUTING)
            runtime.state_store(root).save(work)
            runtime.event_store(root).append(RuntimeEvent(
                kind=RuntimeEventKind.TOOL_CALL,
                work_unit_id=work.id,
                payload={"call_id": "call-1", "tool_id": "shell.run", "arguments": {"command": "echo hi"}},
            ))
            plan = runtime.recovery_plan(root, work.id)
            self.assertTrue(plan.requires_human_review)
            self.assertFalse(plan.safe_to_resume)
            self.assertEqual(("call-1",), plan.pending_tool_call_ids)
            with self.assertRaises(RuntimeError):
                runtime.resume_work(root, work.id, agent_id="executor")

    def test_failed_work_without_pending_call_is_resumable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = AgentExecutionRuntime()
            work = WorkUnit("work-failed", "retry safely", status=WorkStatus.FAILED)
            runtime.state_store(root).save(work)
            plan = runtime.recovery_plan(root, work.id)
            self.assertEqual("resume", plan.disposition.value)
            self.assertTrue(plan.safe_to_resume)


if __name__ == "__main__":
    unittest.main()
