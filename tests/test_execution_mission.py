import unittest

from core.contracts.execution_mission import (
    ExecutionEvidence,
    ExecutionMission,
    MissionOperation,
    verify_execution_evidence,
)
from core.contracts.github import WorkflowArtifact, WorkflowRun
from runtime.github_actions import GitHubActionsMissionRuntime
from runtime.policy import ExecutionPolicy


class FakeGateway:
    def __init__(self):
        self.dispatched = []
        self.polls = 0

    def get_repository(self, repository):
        from core.contracts.github import GitHubRepository
        return GitHubRepository(repository, "main", False)

    def dispatch_workflow(self, repository, workflow, ref, inputs):
        self.dispatched.append((repository, workflow, ref, inputs))
        return WorkflowRun(
            42, "in_progress", None, "main-tip-sha", "https://example/run/42"
        )

    def get_workflow_run(self, repository, run_id):
        self.polls += 1
        return WorkflowRun(
            run_id, "completed", "success",
            "main-tip-sha", "https://example/run/42"
        )

    def list_workflow_artifacts(self, repository, run_id):
        return [WorkflowArtifact(7, "execution-mission-evidence")]

    def get_workflow_artifact_json(self, repository, run_id, artifact_name, filename):
        inputs = self.dispatched[0][3]
        return {
            "mission_id": inputs["mission_id"],
            "run_id": run_id,
            "source_sha": inputs["source_sha"],
            "operation": inputs["operation"],
            "status": "completed",
            "conclusion": "success",
        }


class ExecutionMissionTests(unittest.TestCase):
    def mission(self):
        return ExecutionMission(
            id="mission-abc123",
            repository="eaglesjo/MultiAgentOS",
            source_sha="0123456789abcdef0123456789abcdef01234567",
            workflow="execution-mission.yml",
            operation=MissionOperation.TEST,
            expected_artifacts=("execution-mission-evidence",),
        )

    def test_policy_blocks_actions_by_default(self):
        gateway = FakeGateway()
        runtime = GitHubActionsMissionRuntime(gateway)
        with self.assertRaises(PermissionError):
            runtime.run(self.mission())

    def test_dispatch_and_verify_exact_source(self):
        gateway = FakeGateway()
        policy = ExecutionPolicy(allow_github_actions=True)
        runtime = GitHubActionsMissionRuntime(
            gateway, policy, poll_interval_seconds=0, sleep=lambda _: None
        )
        result = runtime.run(self.mission())
        self.assertEqual(result.evidence.run_id, 42)
        self.assertEqual(result.evidence.conclusion, "success")
        self.assertEqual(result.evidence.source_sha, self.mission().source_sha)
        self.assertEqual(result.evidence.head_sha, "main-tip-sha")
        self.assertEqual(gateway.dispatched[0][2], "main")
        self.assertEqual(
            gateway.dispatched[0][3]["source_sha"], self.mission().source_sha
        )

    def test_artifact_run_id_mismatch_is_rejected(self):
        class MismatchedRunIdGateway(FakeGateway):
            def get_workflow_artifact_json(self, repository, run_id, artifact_name, filename):
                payload = super().get_workflow_artifact_json(
                    repository, run_id, artifact_name, filename
                )
                payload["run_id"] = run_id + 1
                return payload

        gateway = MismatchedRunIdGateway()
        runtime = GitHubActionsMissionRuntime(
            gateway,
            ExecutionPolicy(allow_github_actions=True),
            poll_interval_seconds=0,
            sleep=lambda _: None,
        )
        with self.assertRaisesRegex(ValueError, "run_id"):
            runtime.run(self.mission())

    def test_artifact_source_sha_mismatch_is_rejected(self):
        class MismatchedSourceGateway(FakeGateway):
            def get_workflow_artifact_json(self, repository, run_id, artifact_name, filename):
                payload = super().get_workflow_artifact_json(
                    repository, run_id, artifact_name, filename
                )
                payload["source_sha"] = "f" * 40
                return payload

        runtime = GitHubActionsMissionRuntime(
            MismatchedSourceGateway(),
            ExecutionPolicy(allow_github_actions=True),
            poll_interval_seconds=0,
            sleep=lambda _: None,
        )
        with self.assertRaisesRegex(ValueError, "source_sha"):
            runtime.run(self.mission())

    def test_artifact_mission_identity_mismatch_is_rejected(self):
        class MismatchedMissionGateway(FakeGateway):
            def get_workflow_artifact_json(self, repository, run_id, artifact_name, filename):
                payload = super().get_workflow_artifact_json(
                    repository, run_id, artifact_name, filename
                )
                payload["mission_id"] = "another-mission"
                return payload

        runtime = GitHubActionsMissionRuntime(
            MismatchedMissionGateway(),
            ExecutionPolicy(allow_github_actions=True),
            poll_interval_seconds=0,
            sleep=lambda _: None,
        )
        with self.assertRaisesRegex(ValueError, "mission_id"):
            runtime.run(self.mission())

    def test_source_mismatch_is_rejected(self):
        mission = self.mission()
        evidence = ExecutionEvidence(
            mission_id=mission.id,
            run_id=42,
            status="completed",
            conclusion="success",
            head_sha="main-tip-sha",
            source_sha="bad-source",
        )
        with self.assertRaises(ValueError):
            verify_execution_evidence(mission, evidence)


if __name__ == "__main__":
    unittest.main()
