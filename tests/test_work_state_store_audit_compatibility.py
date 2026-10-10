"""Regression tests for durable structured tool-result audit metadata."""

import json
import tempfile
import unittest
from pathlib import Path

from core.contracts.work_unit import WorkStatus, WorkUnit
from core.state import WorkStateStore


class WorkStateStoreAuditCompatibilityTests(unittest.TestCase):
    def test_structured_tool_audit_survives_state_store_reload(self):
        with tempfile.TemporaryDirectory() as temp:
            store = WorkStateStore(Path(temp) / "work")
            audit = [
                {
                    "tool_id": "execution.route.select",
                    "ok": True,
                    "output": {"route": "github_actions"},
                    "error": None,
                    "metadata": {"decision_id": "decision-1"},
                },
                {
                    "tool_id": "github.actions.run_mission",
                    "ok": False,
                    "output": {
                        "run_id": 42,
                        "source_sha": "0123456789abcdef0123456789abcdef01234567",
                        "artifacts": [],
                    },
                    "error": "expected evidence artifact was missing",
                    "metadata": {"mission_id": "mission-wu-audit"},
                },
            ]
            work = WorkUnit(
                id="wu-audit-roundtrip",
                objective="run and audit a mission",
                status=WorkStatus.FAILED,
                metadata={
                    "tool_results_audit": audit,
                    "tool_error": "expected evidence artifact was missing",
                },
            )

            store.save(work)
            reloaded = store.load(work.id)

        self.assertEqual(reloaded.status, WorkStatus.FAILED)
        self.assertEqual(reloaded.metadata["tool_results_audit"], audit)
        self.assertEqual(
            reloaded.metadata["tool_results_audit"][1]["output"]["source_sha"],
            "0123456789abcdef0123456789abcdef01234567",
        )
        self.assertEqual(
            reloaded.metadata["tool_results_audit"][1]["error"],
            "expected evidence artifact was missing",
        )

    def test_legacy_work_unit_without_tool_audit_still_loads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "work"
            root.mkdir()
            (root / "wu-legacy.json").write_text(
                json.dumps(
                    {
                        "id": "wu-legacy",
                        "objective": "legacy saved task",
                        "status": "completed",
                        "metadata": {"model_response": "done"},
                    }
                ),
                encoding="utf-8",
            )

            reloaded = WorkStateStore(root).load("wu-legacy")

        self.assertEqual(reloaded.status, WorkStatus.COMPLETED)
        self.assertEqual(reloaded.metadata, {"model_response": "done"})
        self.assertNotIn("tool_results_audit", reloaded.metadata)


if __name__ == "__main__":
    unittest.main()
