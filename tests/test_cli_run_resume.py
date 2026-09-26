import tempfile
import unittest
from pathlib import Path

from core.contracts.work_unit import WorkStatus, WorkUnit
from multiagentos.cli import main
from runtime.vyrelon import VYRELONRuntime


class CLIRunResumeTests(unittest.TestCase):
    def test_run_persists_completed_work_unit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work_id = "cli-run"
            result = main(
                [
                    "run",
                    str(root),
                    "--id",
                    work_id,
                    "--objective",
                    "run a command",
                    "--command",
                    "python",
                    "-c",
                    "print('hello')",
                ]
            )
            self.assertEqual(result, 0)

            work = VYRELONRuntime().state_store(root).load(work_id)
            self.assertEqual(work.status, WorkStatus.COMPLETED)
            self.assertEqual(work.metadata["returncode"], 0)
            self.assertEqual(work.metadata["stdout"], "hello\n")

    def test_resume_executes_persisted_executing_work_unit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = VYRELONRuntime().state_store(root)
            work = WorkUnit("cli-resume", "resume a command")
            work.transition(WorkStatus.EXECUTING)
            work.metadata["command"] = ["python", "-c", "print('resumed')"]
            store.save(work)

            result = main(["resume", work.id, str(root)])

            self.assertEqual(result, 0)
            restored = store.load(work.id)
            self.assertEqual(restored.status, WorkStatus.COMPLETED)
            self.assertEqual(restored.metadata["stdout"], "resumed\n")


if __name__ == "__main__":
    unittest.main()
