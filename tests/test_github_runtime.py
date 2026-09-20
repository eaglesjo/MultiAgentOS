import unittest

from runtime.github import GitHubRuntime
from runtime.policy import ExecutionPolicy


class FakeGateway:
    def __init__(self):
        self.calls = []

    def create_branch(self, *args):
        self.calls.append(("branch", args))
        return "branch"

    def create_file(self, *args):
        self.calls.append(("create_file", args))
        return "created"

    def update_file(self, *args):
        self.calls.append(("update_file", args))
        return "updated"

    def create_issue(self, *args):
        self.calls.append(("issue", args))
        return "issue"

    def create_pull_request(self, *args):
        self.calls.append(("pr", args))
        return "pr"

    def review_pull_request(self, *args):
        self.calls.append(("review", args))
        return "review"

    def merge_pull_request(self, *args):
        self.calls.append(("merge", args))
        return "merge"


class GitHubRuntimeTests(unittest.TestCase):
    def test_write_requires_policy(self):
        runtime = GitHubRuntime(FakeGateway())
        with self.assertRaises(PermissionError):
            runtime.create_branch("owner/repo", "feature", "main")

    def test_pr_requires_explicit_approval(self):
        policy = ExecutionPolicy(allow_github_write=True)
        runtime = GitHubRuntime(FakeGateway(), policy)
        with self.assertRaises(PermissionError):
            runtime.create_pull_request("owner/repo", "title", "body", "feature", "main")

    def test_merge_requires_explicit_approval(self):
        policy = ExecutionPolicy(allow_github_write=True)
        runtime = GitHubRuntime(FakeGateway(), policy)
        with self.assertRaises(PermissionError):
            runtime.merge_pull_request("owner/repo", 1)

    def test_approved_write_is_forwarded(self):
        policy = ExecutionPolicy(allow_github_write=True)
        gateway = FakeGateway()
        runtime = GitHubRuntime(gateway, policy)
        self.assertEqual(
            runtime.create_pull_request(
                "owner/repo", "title", "body", "feature", "main", approved=True
            ),
            "pr",
        )
        self.assertEqual(gateway.calls[0][0], "pr")


if __name__ == "__main__":
    unittest.main()
