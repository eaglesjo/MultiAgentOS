import unittest
from unittest.mock import patch

from integrations.github.gateway import GitHubGatewayClient


class GitHubGatewayDispatchTests(unittest.TestCase):
    @patch.object(GitHubGatewayClient, "_run")
    def test_dispatch_requests_run_details(self, run):
        run.side_effect = [
            {"workflow_run_id": 12345},
            {
                "databaseId": 12345,
                "status": "queued",
                "conclusion": None,
                "headSha": "a" * 40,
                "url": "https://github.com/eaglesjo/MultiAgentOS/actions/runs/12345",
            },
        ]

        result = GitHubGatewayClient().dispatch_workflow(
            "eaglesjo/MultiAgentOS",
            "execution-mission.yml",
            "main",
            {
                "mission_id": "mission-test",
                "source_sha": "b" * 40,
                "operation": "test",
            },
        )

        self.assertEqual(result.run_id, 12345)
        dispatch_args = run.call_args_list[0].args
        self.assertIn("-F", dispatch_args)
        self.assertIn("return_run_details=true", dispatch_args)


if __name__ == "__main__":
    unittest.main()
