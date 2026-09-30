import io
from importlib.metadata import PackageNotFoundError, version
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from multiagentos.cli import build_parser
from runtime.mcp.server import AgentExecutionRuntimeMCPServer, AgentExecutionRuntimeMCPServer


class AgentExecutionRuntimeMCPServerTests(unittest.TestCase):
    def test_canonical_server_is_concrete_implementation(self):
        self.assertEqual(AgentExecutionRuntimeMCPServer.__name__, "AgentExecutionRuntimeMCPServer")
        self.assertTrue(issubclass(AgentExecutionRuntimeMCPServer, AgentExecutionRuntimeMCPServer))

    def test_cli_exposes_mcp_serve(self):
        args = build_parser().parse_args(["mcp", "serve", "--path", "/tmp/project"])
        self.assertEqual(args.command, "mcp")
        self.assertEqual(args.mcp_command, "serve")
        self.assertFalse(args.allow_write)
        self.assertFalse(args.allow_process)

    def test_default_server_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "hello.txt").write_text("hello", encoding="utf-8")
            server = AgentExecutionRuntimeMCPServer(root)
            tools = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            names = {item["name"] for item in tools["result"]["tools"]}
            self.assertIn("filesystem.read", names)
            self.assertNotIn("filesystem.write", names)
            self.assertNotIn("patch.apply", names)
            self.assertNotIn("shell.run", names)

            response = server.handle({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "filesystem.read", "arguments": {"path": "hello.txt"}},
            })
            self.assertFalse(response["result"]["isError"])
            self.assertEqual(response["result"]["content"][0]["text"], "hello")

    def test_write_and_process_require_explicit_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            server = AgentExecutionRuntimeMCPServer(root, allow_write=True, allow_process=True)
            tools = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            names = {item["name"] for item in tools["result"]["tools"]}
            self.assertTrue({"filesystem.write", "patch.apply", "shell.run"} <= names)

    def test_patch_apply_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "README.md"
            target.write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.email=test@example.com",
                    "-c",
                    "user.name=Test",
                    "commit",
                    "-m",
                    "initial",
                ],
                cwd=root,
                check=True,
                capture_output=True,
            )
            server = AgentExecutionRuntimeMCPServer(root, allow_write=True)

            patch = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-before
+after
"""

            response = server.handle({
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "patch.apply",
                    "arguments": {"patch": patch},
                },
            })

            self.assertFalse(response["result"]["isError"])
            payload = json.loads(response["result"]["content"][0]["text"])
            self.assertEqual(payload["returncode"], 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "after\n")

    def test_stdio_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "hello.txt").write_text("hello", encoding="utf-8")
            payload = "\n".join([
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
                json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "filesystem.read", "arguments": {"path": "hello.txt"}}}),
            ]) + "\n"
            stdin = io.StringIO(payload)
            stdout = io.StringIO()
            AgentExecutionRuntimeMCPServer(root).serve_forever(stdin, stdout)
            responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
            self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "Agent Execution Runtime")
            try:
                expected_version = version("multiagentos")
            except PackageNotFoundError:
                expected_version = "0.0.0-dev"
            self.assertEqual(
                responses[0]["result"]["serverInfo"]["version"],
                expected_version,
            )
            self.assertIn("filesystem.read", {x["name"] for x in responses[1]["result"]["tools"]})
            self.assertEqual(responses[2]["result"]["content"][0]["text"], "hello")


if __name__ == "__main__":
    unittest.main()
