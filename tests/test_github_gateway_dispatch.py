import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from integrations.github.gateway import GitHubGatewayClient


class GitHubGatewayDispatchTests(unittest.TestCase):
    @patch("integrations.github.gateway.subprocess.run")
    def test_artifact_json_download_parses_run_owned_payload(self, run):
        payload = {
            "mission_id": "mission-test",
            "run_id": 12345,
            "source_sha": "b" * 40,
            "operation": "test",
            "status": "completed",
            "conclusion": "success",
        }

        def fake_download(args, **kwargs):
            output_dir = Path(args[args.index("--dir") + 1])
            (output_dir / "result.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            return __import__("subprocess").CompletedProcess(
                args, 0, stdout="Downloaded artifact", stderr=""
            )

        run.side_effect = fake_download
        result = GitHubGatewayClient().get_workflow_artifact_json(
            "eaglesjo/MultiAgentOS",
            12345,
            "execution-mission-evidence",
            "result.json",
        )

        self.assertEqual(result, payload)
        self.assertIn("run", run.call_args.args[0])
        self.assertIn("12345", run.call_args.args[0])

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

        self.assertEqual(result.id, 12345)
        dispatch_args = run.call_args_list[0].args
        self.assertIn("-F", dispatch_args)
        self.assertIn("return_run_details=true", dispatch_args)


if __name__ == "__main__":
    unittest.main()
