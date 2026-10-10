"""Regression tests for traversal in durable audit stores."""

import tempfile
import unittest
from pathlib import Path

from core.contracts.policy_decision import (
    DecisionCategory,
    DecisionDisposition,
    PolicyDecision,
)
from core.contracts.recovery import RecoveryDisposition, RecoveryPlan
from core.policy_decision import PolicyDecisionStore
from core.recovery_audit import RecoveryAuditStore


class DurableAuditPathSecurityTests(unittest.TestCase):
    def test_load_and_append_reject_invalid_work_unit_ids(self):
        invalid_ids = ("../outside", r"..\\outside", "bad:stream", "", ".", "..", "bad\x00id")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            recovery = RecoveryAuditStore(root / "recovery")
            decisions = PolicyDecisionStore(root / "decisions")

            for work_unit_id in invalid_ids:
                with self.subTest(store="recovery", work_unit_id=repr(work_unit_id)):
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        recovery.load(work_unit_id)
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        recovery.append(RecoveryPlan(
                            work_unit_id,
                            RecoveryDisposition.RESUME,
                            safe_to_resume=True,
                            reason="test",
                        ))

                with self.subTest(store="policy", work_unit_id=repr(work_unit_id)):
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        decisions.load(work_unit_id)
                    with self.assertRaisesRegex(ValueError, "invalid state identifier"):
                        decisions.append(PolicyDecision(
                            work_unit_id=work_unit_id,
                            category=DecisionCategory.APPROVAL,
                            disposition=DecisionDisposition.DENY,
                            reason="test",
                        ))

    def test_audit_stores_reject_symlink_escape_for_reads_and_appends(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root / "outside.jsonl"
            outside.write_text('{"sentinel":"unchanged"}\\n', encoding="utf-8")
            recovery_root = root / "recovery"
            decision_root = root / "decisions"
            recovery_root.mkdir()
            decision_root.mkdir()

            links = (
                recovery_root / "work-1.jsonl",
                decision_root / "work-1.jsonl",
            )
            try:
                for link in links:
                    link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable in this environment")

            recovery = RecoveryAuditStore(recovery_root)
            decisions = PolicyDecisionStore(decision_root)
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                recovery.load("work-1")
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                recovery.append(RecoveryPlan(
                    "work-1",
                    RecoveryDisposition.RESUME,
                    safe_to_resume=True,
                    reason="test",
                ))
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                decisions.load("work-1")
            with self.assertRaisesRegex(ValueError, "state path escapes configured root"):
                decisions.append(PolicyDecision(
                    work_unit_id="work-1",
                    category=DecisionCategory.APPROVAL,
                    disposition=DecisionDisposition.DENY,
                    reason="test",
                ))

            self.assertEqual(outside.read_text(encoding="utf-8"), '{"sentinel":"unchanged"}\\n')


if __name__ == "__main__":
    unittest.main()
