import json
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

from core.contracts.repository import RepositoryCheckpoint
from runtime.git import GitRuntime
from runtime.github import GitHubRuntime
from runtime.policy import ExecutionPolicy
from runtime.repository import RepositoryRuntime


class FakeGateway:
    def list_workflows(self, repository, ref):
        return ({"repository": repository, "ref": ref, "status": "completed"},)


class RepositoryRuntimeTests(TestCase):
    def _git_repo(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        return tmp, root

    def test_checkpoint_and_recover(self):
        tmp, root = self._git_repo()
        try:
            (root / "sample.txt").write_text("before")
            subprocess.run(["git", "add", "sample.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
            (root / "sample.txt").write_text("after")
            runtime = RepositoryRuntime(
                GitRuntime(policy=ExecutionPolicy(allow_git_write=True)),
                GitHubRuntime(FakeGateway(), ExecutionPolicy()),
                ExecutionPolicy(allow_git_write=True),
            )
            checkpoint = runtime.checkpoint(root)
            self.assertTrue(checkpoint.metadata["stashed"])
            (root / "sample.txt").write_text("changed-again")
            recovery = runtime.recover(root, checkpoint)
            self.assertTrue(recovery.restored)
            self.assertEqual((root / "sample.txt").read_text(), "after")
        finally:
            tmp.cleanup()

    def test_clean_checkpoint_is_safe(self):
        tmp, root = self._git_repo()
        try:
            runtime = RepositoryRuntime(
                GitRuntime(policy=ExecutionPolicy(allow_git_write=True)),
                GitHubRuntime(FakeGateway(), ExecutionPolicy()),
                ExecutionPolicy(allow_git_write=True),
            )
            checkpoint = runtime.checkpoint(root)
            self.assertFalse(checkpoint.metadata["stashed"])
            recovery = runtime.recover(root, checkpoint)
            self.assertTrue(recovery.restored)
        finally:
            tmp.cleanup()

    def test_evidence_is_persisted(self):
        tmp, root = self._git_repo()
        try:
            runtime = RepositoryRuntime(
                GitRuntime(policy=ExecutionPolicy()),
                GitHubRuntime(FakeGateway(), ExecutionPolicy()),
                ExecutionPolicy(),
            )
            evidence = runtime.evidence(root, repository="example/repo", ref="main")
            path = root / ".multiagentos/evidence/repository.json"
            self.assertTrue(path.exists())
            self.assertIn("git_status", json.loads(path.read_text()))
            self.assertEqual(evidence.workflows[0]["status"], "completed")
        finally:
            tmp.cleanup()
