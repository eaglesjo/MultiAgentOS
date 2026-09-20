import unittest
from unittest.mock import patch

from runtime.git import GitRuntime
from runtime.policy import ExecutionPolicy
from runtime.process import ProcessRuntime


class RuntimeAdapterTests(unittest.TestCase):
    def test_process_requires_policy(self):
        runtime = ProcessRuntime(ExecutionPolicy(allow_process=False))
        with self.assertRaises(PermissionError):
            runtime.run(["echo", "ok"])

    def test_git_write_requires_policy(self):
        runtime = GitRuntime(policy=ExecutionPolicy(allow_git_write=False))
        with self.assertRaises(PermissionError):
            runtime.checkout_branch(".", "main")

    def test_git_commit_requires_approval(self):
        policy = ExecutionPolicy(allow_git_write=True)
        runtime = GitRuntime(policy=policy)
        with self.assertRaises(PermissionError):
            runtime.commit(".", "test", approved=False)

    def test_git_push_requires_approval(self):
        policy = ExecutionPolicy(allow_git_write=True)
        runtime = GitRuntime(policy=policy)
        with self.assertRaises(PermissionError):
            runtime.push(".", approved=False)

    def test_process_result(self):
        runtime = ProcessRuntime()
        with patch("subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "ok"
            run.return_value.stderr = ""
            result = runtime.run(["echo", "ok"])
        self.assertEqual(result.stdout, "ok")


if __name__ == "__main__":
    unittest.main()
