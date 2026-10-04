"""Terminal MCP acceptance tests for the Cost-Free local execution path."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime.mcp.server import AgentExecutionRuntimeMCPServer


def _tool_text(response: dict[str, object]) -> str:
    result = response["result"]
    assert isinstance(result, dict)
    content = result["content"]
    assert isinstance(content, list)
    first = content[0]
    assert isinstance(first, dict)
    return str(first["text"])


class TerminalMCPAcceptanceTests(unittest.TestCase):
    """Verify the complete currently supported foreground shell contract."""

    def test_process_permission_hides_shell_tool_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            server = AgentExecutionRuntimeMCPServer(Path(temp))
            response = server.handle(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
            )
            self.assertIsNotNone(response)
            names = {item["name"] for item in response["result"]["tools"]}
            self.assertNotIn("shell.run", names)

    def test_tools_list_exposes_shell_only_with_process_permission(self):
        with tempfile.TemporaryDirectory() as temp:
            server = AgentExecutionRuntimeMCPServer(
                Path(temp), allow_process=True
            )
            response = server.handle(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
            )
            self.assertIsNotNone(response)
            names = {item["name"] for item in response["result"]["tools"]}
            self.assertIn("shell.run", names)

    def test_shell_run_executes_command_in_project_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            server = AgentExecutionRuntimeMCPServer(root, allow_process=True)
            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "shell.run",
                        "arguments": {"command": "pwd"},
                    },
                }
            )
            self.assertFalse(response["result"]["isError"])
            payload = json.loads(_tool_text(response))
            self.assertEqual(payload["returncode"], 0)
            self.assertEqual(Path(payload["cwd"]).resolve(), root)
            self.assertEqual(Path(payload["stdout"].strip()).resolve(), root)
            self.assertEqual(payload["stderr"], "")

    def test_shell_run_preserves_stdout_stderr_and_exit_code(self):
        with tempfile.TemporaryDirectory() as temp:
            server = AgentExecutionRuntimeMCPServer(
                Path(temp), allow_process=True
            )
            command = (
                f'{sys.executable} -c '
                '"import sys; print(\'stdout-ok\'); print(\'stderr-ok\', file=sys.stderr); sys.exit(7)"'
            )
            response = server.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "shell.run",
                        "arguments": {"command": command},
                    },
                }
            )
            self.assertFalse(response["result"]["isError"])
            payload = json.loads(_tool_text(response))
            self.assertEqual(payload["returncode"], 7)
            self.assertIn("stdout-ok", payload["stdout"])
            self.assertIn("stderr-ok", payload["stderr"])

    def test_stdio_mcp_process_path_executes_shell_command(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "multiagentos.cli",
                    "mcp",
                    "serve",
                    "--path",
                    str(root),
                    "--allow-process",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            def send(message: dict[str, object]) -> dict[str, object]:
                assert proc.stdin is not None
                assert proc.stdout is not None
                proc.stdin.write(json.dumps(message) + "\n")
                proc.stdin.flush()
                line = proc.stdout.readline()
                self.assertTrue(line, "MCP server closed stdout unexpectedly")
                return json.loads(line)

            try:
                initialized = send(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {},
                    }
                )
                self.assertEqual(
                    initialized["result"]["serverInfo"]["name"],
                    "Agent Execution Runtime",
                )

                listed = send(
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
                )
                names = {item["name"] for item in listed["result"]["tools"]}
                self.assertIn("shell.run", names)

                executed = send(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "shell.run",
                            "arguments": {"command": "git --version"},
                        },
                    }
                )
                self.assertFalse(executed["result"]["isError"])
                payload = json.loads(_tool_text(executed))
                self.assertEqual(payload["returncode"], 0)
                self.assertIn("git version", payload["stdout"])
            finally:
                proc.terminate()
                proc.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
