import unittest

from core.contracts.execution_mission import ExecutionEvidence
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.execution_route import ExecutionRoute
from runtime.work_unit_execution import AutomaticWorkUnitExecutor, LocalExecutionUnavailable


class AutomaticWorkUnitExecutionTests(unittest.TestCase):
    def evidence(self, mission_id="mission-work-1", success=True):
        return ExecutionEvidence(
            mission_id=mission_id,
            run_id=123,
            status="completed",
            conclusion="success" if success else "failure",
            head_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            source_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            artifacts=("execution-mission-evidence",),
            logs_available=True,
        )

    def test_local_execution_is_preferred(self):
        unit = WorkUnit("work-1", "run local work")
        calls = []

        result = AutomaticWorkUnitExecutor(allow_github_actions=True).execute(
            unit,
            local=lambda work: calls.append(work.id) or "local-result",
            remote=lambda work: (_ for _ in ()).throw(AssertionError("remote was called")),
        )

        self.assertEqual(result.route, ExecutionRoute.LOCAL)
        self.assertEqual(result.output, "local-result")
        self.assertEqual(calls, ["work-1"])
        self.assertEqual(unit.status, WorkStatus.COMPLETED)

    def test_local_failure_falls_back_to_one_remote_mission(self):
        unit = WorkUnit("work-2", "fallback")
        calls = []

        def local(_):
            calls.append("local")
            raise LocalExecutionUnavailable("local runner unavailable")

        def remote(work):
            calls.append("remote")
            return "remote-result", self.evidence(mission_id="mission-work-2")

        result = AutomaticWorkUnitExecutor(allow_github_actions=True).execute(
            unit, local=local, remote=remote
        )

        self.assertEqual(result.route, ExecutionRoute.GITHUB_ACTIONS)
        self.assertEqual(result.output, "remote-result")
        self.assertEqual(calls, ["local", "remote"])
        self.assertEqual(unit.status, WorkStatus.COMPLETED)
        self.assertEqual(unit.metadata["execution_route"], "github_actions")
        self.assertEqual(unit.metadata["execution_evidence"]["mission_id"], "mission-work-2")

    def test_local_execution_failure_does_not_fall_back_automatically(self):
        unit = WorkUnit("work-unsafe-fallback", "test failure must not be retried remotely")
        remote_calls = []

        with self.assertRaisesRegex(RuntimeError, "tests failed"):
            AutomaticWorkUnitExecutor(allow_github_actions=True).execute(
                unit,
                local=lambda _: (_ for _ in ()).throw(RuntimeError("tests failed")),
                remote=lambda work: remote_calls.append(work.id) or ("remote", self.evidence()),
            )

        self.assertEqual(remote_calls, [])
        self.assertEqual(unit.status, WorkStatus.FAILED)

    def test_remote_route_requires_explicit_permission(self):
        unit = WorkUnit("work-3", "blocked")

        with self.assertRaisesRegex(PermissionError, "GitHub Actions is disabled"):
            AutomaticWorkUnitExecutor(allow_github_actions=False).execute(
                unit, local=None, remote=lambda work: ("x", self.evidence()), force_remote=True
            )

        self.assertEqual(unit.status, WorkStatus.BLOCKED)
        self.assertEqual(unit.metadata["execution_route"], "blocked")
        self.assertIn("GitHub Actions is disabled", unit.metadata["execution_block_reason"])

    def test_remote_success_can_execute_without_local(self):
        unit = WorkUnit("work-4", "remote")
        result = AutomaticWorkUnitExecutor(allow_github_actions=True).execute(
            unit,
            local_available=False,
            remote=lambda work: ("remote", self.evidence(mission_id="mission-work-4")),
        )
        self.assertEqual(result.route, ExecutionRoute.GITHUB_ACTIONS)
        self.assertEqual(unit.status, WorkStatus.COMPLETED)

    def test_missing_local_runner_marks_work_unit_failed(self):
        unit = WorkUnit("work-missing-local", "missing local runner")

        with self.assertRaisesRegex(ValueError, "local execution route requires a local runner"):
            AutomaticWorkUnitExecutor(allow_github_actions=False).execute(
                unit, local=None
            )

        self.assertEqual(unit.status, WorkStatus.FAILED)
        self.assertEqual(unit.metadata["execution_route"], "local")
        self.assertIn("execution_error", unit.metadata)

    def test_missing_remote_runner_marks_work_unit_failed(self):
        unit = WorkUnit("work-missing-remote", "missing remote runner")

        with self.assertRaisesRegex(ValueError, "requires a bounded remote runner"):
            AutomaticWorkUnitExecutor(allow_github_actions=True).execute(
                unit, local_available=False, remote=None
            )

        self.assertEqual(unit.status, WorkStatus.FAILED)
        self.assertEqual(unit.metadata["execution_route"], "github_actions")
        self.assertIn("execution_error", unit.metadata)

    def test_remote_runner_exception_marks_work_unit_failed(self):
        unit = WorkUnit("work-remote-exception", "remote failure lifecycle")

        def remote(_):
            raise RuntimeError("GitHub dispatch failed")

        with self.assertRaisesRegex(RuntimeError, "GitHub dispatch failed"):
            AutomaticWorkUnitExecutor(allow_github_actions=True).execute(
                unit, local_available=False, remote=remote
            )

        self.assertEqual(unit.status, WorkStatus.FAILED)
        self.assertEqual(unit.metadata["remote_execution_error"], "GitHub dispatch failed")

    def test_remote_failure_marks_work_unit_failed(self):
        unit = WorkUnit("work-5", "remote failure")
        result = AutomaticWorkUnitExecutor(allow_github_actions=True).execute(
            unit,
            local_available=False,
            remote=lambda work: ("remote", self.evidence(mission_id="mission-work-5", success=False)),
        )
        self.assertEqual(result.route, ExecutionRoute.GITHUB_ACTIONS)
        self.assertEqual(unit.status, WorkStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
