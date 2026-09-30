"""End-to-end stdio smoke client for the AGENT_EXECUTION_RUNTIME MCP server.

This intentionally uses only Python's standard library so the validation path
does not depend on an OpenAI account, ChatGPT subscription, or an MCP SDK.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _send(proc: subprocess.Popen[str], message: dict[str, object]) -> dict[str, object]:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("AGENT_EXECUTION_RUNTIME MCP server closed stdout unexpectedly")
    response = json.loads(line)
    if not isinstance(response, dict):
        raise RuntimeError("MCP response is not a JSON object")
    return response


def _notify(proc: subprocess.Popen[str], message: dict[str, object]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def run_smoke() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "mcp-smoke.txt").write_text("AGENT_EXECUTION_RUNTIME MCP OK", encoding="utf-8")

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "multiagentos.cli",
                "mcp",
                "serve",
                "--path",
                str(root),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            initialized = _send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "agent_execution_runtime-mcp-smoke", "version": "1.0"},
                    },
                },
            )
            assert initialized["result"]["serverInfo"]["name"] == "Agent Execution Runtime"

            _notify(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

            listed = _send(
                proc,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            names = {tool["name"] for tool in listed["result"]["tools"]}
            assert "filesystem.read" in names
            assert "filesystem.write" not in names
            assert "patch.apply" not in names
            assert "shell.run" not in names

            read = _send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "filesystem.read",
                        "arguments": {"path": "mcp-smoke.txt"},
                    },
                },
            )
            assert read["result"]["isError"] is False
            assert read["result"]["content"][0]["text"] == "AGENT_EXECUTION_RUNTIME MCP OK"
        finally:
            proc.terminate()
            proc.wait(timeout=5)


if __name__ == "__main__":
    run_smoke()
    print("AGENT_EXECUTION_RUNTIME MCP stdio smoke: PASS")
