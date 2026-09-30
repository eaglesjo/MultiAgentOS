import tempfile
import unittest
from pathlib import Path

from core.contracts.recovery import RecoveryDisposition, RecoveryPlan
from core.contracts.work_unit import WorkUnit
from core.recovery_audit import RecoveryAuditStore
from runtime import AgentExecutionRuntime


class RecoveryAuditSourceGuardTests(unittest.TestCase):
    def test_recovery_audit_is_append_only(self):
        with tempfile.TemporaryDirectory() as temp:
            store = RecoveryAuditStore(Path(temp))
            plan = RecoveryPlan("work-1", RecoveryDisposition.RESUME, safe_to_resume=True, reason="safe")
            store.append(plan, source_identity={"head": "abc", "dirty": False})
            store.append(plan, source_identity={"head": "abc", "dirty": False})
            records = store.load("work-1")
            self.assertEqual(len(records), 2)
            self.assertEqual(records[-1]["disposition"], "resume")

    def test_recovery_requires_review_when_workspace_identity_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = AgentExecutionRuntime()
            work = WorkUnit(
                "work-1",
                "resume",
                metadata={"source_identity": {"head": "expected-head", "dirty": False}},
            )
            runtime.state_store(root).save(work)
            plan = runtime.recovery_plan(root, "work-1")
            self.assertEqual(plan.disposition, RecoveryDisposition.REVIEW_REQUIRED)
            self.assertIn("source identity changed", plan.reason)


if __name__ == "__main__":
    unittest.main()
