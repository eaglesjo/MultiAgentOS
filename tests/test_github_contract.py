import unittest

from core.contracts.github import GitHubBranch, GitHubFile, GitHubRepository, PullRequest


class GitHubContractTests(unittest.TestCase):
    def test_repository(self):
        self.assertEqual(GitHubRepository("eaglesjo/MultiAgentOS", "main", True).default_branch, "main")

    def test_branch(self):
        self.assertEqual(GitHubBranch("main", "abc").name, "main")

    def test_file(self):
        self.assertEqual(GitHubFile("README.md", "hello", "sha").path, "README.md")

    def test_pull_request(self):
        self.assertEqual(PullRequest(1, "test", "url", "feature", "main").base, "main")


if __name__ == "__main__":
    unittest.main()
