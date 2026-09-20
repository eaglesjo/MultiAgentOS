import unittest

from core.contracts import AgentContract, ModelSpec, WorkStatus, WorkUnit
from core.contracts.execution import ReviewDecision
from core.lifecycle import LifecycleError
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


class PassingVerifier:
    def verify(self, *, work_unit, output):
        return True


class FailingVerifier:
    def verify(self, *, work_unit, output):
        return False


class PassingReviewer:
    def review(self, *, work_unit, output):
        return ReviewDecision(approved=True, feedback="approved")


class FailingReviewer:
    def review(self, *, work_unit, output):
        return ReviewDecision(approved=False, feedback="needs changes")


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

    def test_run_verifies_before_completion(self):
        work = WorkUnit("wu-verify", "implement feature")
        result = Orchestrator().run(
            work, self.agent, self.models, RecordingExecutor(),
            verifier=PassingVerifier(),
        )
        self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)

    def test_run_reviews_before_handoff(self):
        work = WorkUnit("wu-review", "implement feature")
        result = Orchestrator().run(
            work, self.agent, self.models, RecordingExecutor(),
            verifier=PassingVerifier(),
            reviewer=PassingReviewer(),
        )
        self.assertEqual(result.work_unit.status, WorkStatus.COMPLETED)

    def test_run_fails_when_verification_fails(self):
        work = WorkUnit("wu-verify-fail", "implement feature")
        with self.assertRaises(LifecycleError):
            Orchestrator().run(
                work, self.agent, self.models, RecordingExecutor(),
                verifier=FailingVerifier(),
            )
        self.assertEqual(work.status, WorkStatus.FAILED)

    def test_run_fails_when_review_rejects(self):
        work = WorkUnit("wu-review-fail", "implement feature")
        with self.assertRaises(LifecycleError):
            Orchestrator().run(
                work, self.agent, self.models, RecordingExecutor(),
                verifier=PassingVerifier(),
                reviewer=FailingReviewer(),
            )
        self.assertEqual(work.status, WorkStatus.FAILED)

    def test_run_marks_execution_failure(self):
        work = WorkUnit("wu-003", "debug feature")
        with self.assertRaises(RuntimeError):
            Orchestrator().run(work, self.agent, self.models, FailingExecutor())
        self.assertEqual(work.status, WorkStatus.FAILED)

    def test_routing_failure_does_not_start_execution(self):
        work = WorkUnit("wu-route", "unroutable")
        incompatible = [ModelSpec("text", "provider-a", frozenset({"text"}))]
        with self.assertRaises(LookupError):
            Orchestrator().run(work, self.agent, incompatible, RecordingExecutor())
        self.assertEqual(work.status, WorkStatus.PENDING)
        self.assertEqual(work.assigned_agents, [])


if __name__ == "__main__":
    unittest.main()
