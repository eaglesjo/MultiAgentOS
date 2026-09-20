import unittest
from unittest.mock import patch

from runtime.github_probe import probe


class GitHubProbeTests(unittest.TestCase):
    def test_probe_uses_vyrelon_gateway(self):
        fake_repo = type("Repo", (), {
            "full_name": "owner/repo",
            "private": False,
            "default_branch": "main",
        })()
        fake_branch = type("Branch", (), {"sha": "abc123"})()

        with patch("runtime.github_probe.GitHubGatewayClient") as client_cls:
            client = client_cls.return_value
            client.get_repository.return_value = fake_repo
            client.get_branch.return_value = fake_branch
            result = probe("owner/repo")

        self.assertEqual(result["repository"], "owner/repo")
        self.assertEqual(result["default_branch"], "main")
        self.assertEqual(result["default_branch_sha"], "abc123")


if __name__ == "__main__":
    unittest.main()
