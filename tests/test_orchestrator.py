import unittest

from core.contracts import AgentContract, ModelSpec, WorkStatus, WorkUnit
from core.orchestrator import Orchestrator


class RecordingExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, *, agent, model_id, work_unit):
        self.calls.append((agent.id, model_id, work_unit.id))
        return {"status": "ok", "model": model_id}


class FailingExecutor:
    def execute(self, **kwargs):
        raise RuntimeError("execution failed")


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.agent = AgentContract(
            id="developer", role="developer",
            capabilities=frozenset({"code"}),
        )
        self.models = [
            ModelSpec("cloud-code", "provider-a", frozenset({"code"})),
            ModelSpec("local-code", "local", frozenset({"code"})),
        ]

    def test_run_delegates_and_completes(self):
        work = WorkUnit("wu-002", "implement feature")
        executor = RecordingExecutor()
        result = Orchestrator().run(
            work, self.agent, self.models, executor, ["cloud-code"]
        )
        self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)
        self.assertEqual(result.delegation.assignment.model_id, "cloud-code")
        self.assertEqual(executor.calls, [("developer", "cloud-code", "wu-002")])

    def test_run_marks_failure(self):
        work = WorkUnit("wu-003", "debug feature")
        with self.assertRaises(RuntimeError):
            Orchestrator().run(work, self.agent, self.models, FailingExecutor())
        self.assertEqual(work.status, WorkStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
