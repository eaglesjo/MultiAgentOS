"""Tests for policy-controlled Git runtime behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.git import GitRuntime
from runtime.policy import ExecutionPolicy


class GitRuntimeTests(unittest.TestCase):
    def test_read_operations_are_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            import subprocess
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            result = GitRuntime(policy=ExecutionPolicy()).status(str(root))
            self.assertEqual(result.returncode, 0)
            self.assertIn("##", result.stdout)

    def test_write_operations_require_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = GitRuntime(policy=ExecutionPolicy(allow_git_write=False))
            with self.assertRaises(PermissionError):
                runtime.add(tmp)

    def test_commit_requires_explicit_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = GitRuntime(
                policy=ExecutionPolicy(
                    allow_git_write=True,
                    require_approval_for=frozenset({"git.commit"}),
                )
            )
            with self.assertRaises(PermissionError):
                runtime.commit(tmp, "blocked")


if __name__ == "__main__":
    unittest.main()
