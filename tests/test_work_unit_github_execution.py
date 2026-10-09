import tempfile
import unittest
from pathlib import Path

from core.contracts.execution_mission import ExecutionEvidence, MissionOperation
from core.contracts.work_unit import WorkStatus, WorkUnit
from runtime.agent_execution_runtime import AgentExecutionRuntime
from runtime.policy import ExecutionPolicy
from runtime.work_unit_execution import LocalExecutionUnavailable


class WorkUnitGitHubExecutionTests(unittest.TestCase):
    def evidence(self, *, mission_id, source_sha, success=True):
        return ExecutionEvidence(
            mission_id=mission_id,
            run_id=99,
            status="completed",
            conclusion="success" if success else "failure",
            head_sha=source_sha,
            source_sha=source_sha,
            artifacts=("execution-mission-evidence",),
            logs_available=True,
        )

    def test_local_success_does_not_dispatch_remote_mission(self):
        runtime = AgentExecutionRuntime(
            policy=ExecutionPolicy(allow_github_actions=True)
        )
        calls = []
        runtime.git.identity = lambda _: {"head": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "dirty": False}
        runtime.github.run_actions_mission = lambda mission: calls.append(mission)

        with tempfile.TemporaryDirectory() as root:
            unit = WorkUnit("work-local", "local first")
            result = runtime.execute_work_unit_with_github_actions(
                unit,
                local=lambda _: "local-result",
                project_root=Path(root),
                repository="eaglesjo/MultiAgentOS",
            )

        self.assertEqual(result.route.value, "local")
        self.assertEqual(result.output, "local-result")
        self.assertEqual(unit.status, WorkStatus.COMPLETED)
        self.assertEqual(calls, [])

    def test_local_failure_dispatches_real_mission_and_verifies_evidence(self):
        runtime = AgentExecutionRuntime(
            policy=ExecutionPolicy(allow_github_actions=True)
        )
        source_sha = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        captured = []

        runtime.git.identity = lambda _: {"head": source_sha, "dirty": False}

        def run_mission(mission):
            captured.append(mission)
            return type(
                "MissionResult",
                (),
                {"evidence": self.evidence(
                    mission_id=mission.id,
                    source_sha=mission.source_sha,
                )},
            )()

        runtime.github.run_actions_mission = run_mission

        with tempfile.TemporaryDirectory() as root:
            unit = WorkUnit("work-remote", "fallback")
            result = runtime.execute_work_unit_with_github_actions(
                unit,
                local=lambda _: (_ for _ in ()).throw(LocalExecutionUnavailable("local runner unavailable")),
                project_root=Path(root),
                repository="eaglesjo/MultiAgentOS",
                operation=MissionOperation.TEST,
            )

        self.assertEqual(result.route.value, "github_actions")
        self.assertEqual(unit.status, WorkStatus.COMPLETED)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].id, "mission-work-remote")
        self.assertEqual(captured[0].source_sha, source_sha)
        self.assertEqual(captured[0].operation, MissionOperation.TEST)
        self.assertEqual(
            unit.metadata["execution_evidence"]["mission_id"],
            "mission-work-remote",
        )

    def test_dirty_worktree_blocks_github_fallback(self):
        runtime = AgentExecutionRuntime(
            policy=ExecutionPolicy(allow_github_actions=True)
        )
        runtime.git.identity = lambda _: {
            "head": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "dirty": True,
        }
        runtime.github.run_actions_mission = lambda mission: self.fail(
            "remote mission must not run from a dirty worktree"
        )

        with tempfile.TemporaryDirectory() as root:
            unit = WorkUnit("work-dirty", "do not ship dirty state")
            with self.assertRaises(PermissionError):
                runtime.execute_work_unit_with_github_actions(
                    unit,
                    local_available=False,
                    local=lambda _: "unused",
                    project_root=Path(root),
                    repository="eaglesjo/MultiAgentOS",
                )

            persisted = runtime.state_store(Path(root)).load("work-dirty")

        self.assertEqual(unit.status, WorkStatus.FAILED)
        self.assertEqual(persisted.status, WorkStatus.FAILED)
        self.assertEqual(
            persisted.metadata["remote_execution_error"],
            "GitHub fallback requires a clean local worktree",
        )

    def test_success_evidence_head_mismatch_fails_closed(self):
        runtime = AgentExecutionRuntime(
            policy=ExecutionPolicy(allow_github_actions=True)
        )
        source_sha = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        runtime.git.identity = lambda _: {"head": source_sha, "dirty": False}
        runtime.github.run_actions_mission = lambda mission: type(
            "MissionResult",
            (),
            {"evidence": ExecutionEvidence(
                mission_id=mission.id,
                run_id=99,
                status="completed",
                conclusion="success",
                head_sha="cccccccccccccccccccccccccccccccccccccccc",
                source_sha=source_sha,
                artifacts=("execution-mission-evidence",),
                logs_available=True,
            )},
        )()

        with tempfile.TemporaryDirectory() as root:
            unit = WorkUnit("work-head-mismatch", "fail closed on head mismatch")
            with self.assertRaisesRegex(ValueError, "head identity mismatch"):
                runtime.execute_work_unit_with_github_actions(
                    unit,
                    local_available=False,
                    local=lambda _: "unused",
                    project_root=Path(root),
                    repository="eaglesjo/MultiAgentOS",
                )
            persisted = runtime.state_store(Path(root)).load(unit.id)

        self.assertEqual(unit.status, WorkStatus.FAILED)
        self.assertEqual(persisted.status, WorkStatus.FAILED)

    def test_success_evidence_source_mismatch_fails_closed(self):
        runtime = AgentExecutionRuntime(
            policy=ExecutionPolicy(allow_github_actions=True)
        )
        runtime.git.identity = lambda _: {
            "head": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "dirty": False,
        }
        runtime.github.run_actions_mission = lambda mission: type(
            "MissionResult",
            (),
            {"evidence": self.evidence(
                mission_id=mission.id,
                source_sha="cccccccccccccccccccccccccccccccccccccccc",
            )},
        )()

        with tempfile.TemporaryDirectory() as root:
            unit = WorkUnit("work-mismatch", "fail closed")
            with self.assertRaises(ValueError):
                runtime.execute_work_unit_with_github_actions(
                    unit,
                    local_available=False,
                    local=lambda _: "unused",
                    project_root=Path(root),
                    repository="eaglesjo/MultiAgentOS",
                )

        self.assertEqual(unit.status, WorkStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
