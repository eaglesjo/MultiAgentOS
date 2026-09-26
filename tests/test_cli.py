import json
import tempfile
import unittest
from pathlib import Path

from multiagentos.cli import main
from runtime.status import project_status


class CLITests(unittest.TestCase):
    def test_detect(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text(
                json.dumps({"dependencies": {"react-native": "0.82.0"}}),
                encoding="utf-8",
            )
            self.assertEqual(main(["detect", str(root)]), 0)

    def test_status_uninitialized(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(main(["status", temp]), 0)
            status = project_status(Path(temp))
            self.assertFalse(status["initialized"])
            self.assertEqual(status["components"], [])

    def test_status_reports_vyrelon_only(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(main(["init", temp, "--component", "vyrelon"]), 0)
            status = project_status(Path(temp))
            self.assertTrue(status["initialized"])
            self.assertEqual(status["components"], ["vyrelon"])
            self.assertEqual(status["agents"], [])

    def test_status_reports_multi_agent_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(main(["init", temp, "--component", "multi-agent"]), 0)
            status = project_status(Path(temp))
            self.assertTrue(status["initialized"])
            self.assertEqual(status["components"], ["multi-agent"])
            self.assertTrue(status["agents"])

    def test_status_reports_durable_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(main(["init", temp, "--component", "vyrelon"]), 0)
            state = root / ".multiagentos" / "state"
            checkpoints = root / ".multiagentos" / "checkpoints"
            state.mkdir()
            checkpoints.mkdir()
            (state / "wu-1.json").write_text(json.dumps({
                "id": "wu-1", "objective": "demo", "status": "executing"
            }), encoding="utf-8")
            (checkpoints / "wu-1.json").write_text(json.dumps({
                "work_unit_id": "wu-1", "workflow": "orchestration",
                "stage": "executing", "status": "executing",
                "next_action": "resume_execution", "sequence": 2,
                "resumable": True
            }), encoding="utf-8")
            status = project_status(root)
            self.assertEqual(status["work_units"][0]["id"], "wu-1")
            self.assertEqual(status["checkpoints"][0]["next_action"], "resume_execution")

    def test_run_executes_command_and_persists_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(
                main(["run", temp, "--objective", "echo smoke test", "--", "python", "-c", "print('ok')"]),
                0,
            )
            status = project_status(root)
            self.assertEqual(len(status["work_units"]), 1)
            self.assertEqual(status["work_units"][0]["status"], "completed")
            self.assertEqual(status["checkpoints"][0]["resumable"], False)

    def test_resume_rejects_terminal_work_unit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(
                main(["run", temp, "--objective", "terminal", "--", "python", "-c", "print('done')"]),
                0,
            )
            work_unit_id = project_status(root)["work_units"][0]["id"]
            with self.assertRaises(ValueError):
                main(["resume", work_unit_id, "--path", temp])

    def test_init(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(main(["init", temp]), 0)
            self.assertTrue((Path(temp) / ".multiagentos" / "profile.json").exists())
            self.assertTrue((Path(temp) / ".multiagentos" / "agents.json").exists())


if __name__ == "__main__":
    unittest.main()
