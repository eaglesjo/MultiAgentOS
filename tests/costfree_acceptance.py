"""COSTFREE-001 acceptance test for a clean installed MultiAgentOS runtime.

This test intentionally uses only the Python standard library plus the
installed MultiAgentOS CLI. It validates the cost-free local path:

install -> init -> VYRELON MCP -> READ -> WRITE -> PATCH -> TEST/process.

No provider API key, MCP SDK, or external AI service is required.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def _send(proc: subprocess.Popen[str], message: dict[str, object]) -> dict[str, object]:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("VYRELON MCP server closed stdout unexpectedly")
    response = json.loads(line)
    if not isinstance(response, dict):
        raise RuntimeError("MCP response is not a JSON object")
    return response


def _call(
    proc: subprocess.Popen[str],
    request_id: int,
    name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    response = _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"invalid MCP result for {name}: {response}")
    if result.get("isError"):
        raise RuntimeError(f"MCP tool failed: {name}: {result}")
    return result


def _text(result: dict[str, object]) -> str:
    content = result.get("content")
    if not isinstance(content, list) or not content:
        raise RuntimeError(f"MCP result has no content: {result}")
    item = content[0]
    if not isinstance(item, dict) or not isinstance(item.get("text"), str):
        raise RuntimeError(f"MCP result content is not text: {result}")
    return item["text"]


def run_acceptance() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "project"
        root.mkdir()

        # Fresh-project bootstrap: the CLI must initialize the project without
        # requiring a provider credential.
        _run(["multiagentos", "init", str(root), "--component", "all"])
        if not (root / ".multiagentos" / "profile.json").is_file():
            raise RuntimeError("project bootstrap did not create profile.json")

        # Patch application uses Git's patch engine, so create a minimal local
        # repository fixture after project initialization.
        _run(["git", "init"], cwd=root)
        (root / "README.md").write_text("before\n", encoding="utf-8")
        _run(["git", "add", "README.md"], cwd=root)
        _run(
            [
                "git",
                "-c",
                "user.email=test@example.com",
                "-c",
                "user.name=MultiAgentOS Acceptance",
                "commit",
                "-m",
                "initial",
            ],
            cwd=root,
        )

        proc = subprocess.Popen(
            [
                "multiagentos",
                "mcp",
                "serve",
                "--path",
                str(root),
                "--allow-write",
                "--allow-process",
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
                        "clientInfo": {
                            "name": "costfree-acceptance",
                            "version": "1.0",
                        },
                    },
                },
            )
            if initialized["result"]["serverInfo"]["name"] != "VYRELON":
                raise RuntimeError("unexpected MCP server identity")

            _send(
                proc,
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
            )

            listed = _send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {},
                },
            )
            names = {tool["name"] for tool in listed["result"]["tools"]}
            required = {"filesystem.read", "filesystem.write", "patch.apply", "shell.run"}
            if not required <= names:
                raise RuntimeError(f"missing cost-free tools: {required - names}")

            _call(
                proc,
                3,
                "filesystem.write",
                {"path": "costfree.txt", "content": "cost-free\n"},
            )
            read = _call(
                proc,
                4,
                "filesystem.read",
                {"path": "costfree.txt"},
            )
            if _text(read) != "cost-free\n":
                raise RuntimeError("filesystem WRITE/READ round-trip failed")

            patch = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-before
+after
"""
            patch_result = json.loads(
                _text(_call(proc, 5, "patch.apply", {"patch": patch}))
            )
            if patch_result["returncode"] != 0 or patch_result["stderr"] != "":
                raise RuntimeError(f"patch.apply failed: {patch_result}")

            readback = _text(
                _call(proc, 6, "filesystem.read", {"path": "README.md"})
            )
            if readback != "after\n":
                raise RuntimeError("patch readback failed")

            shell_result = json.loads(
                _text(
                    _call(
                        proc,
                        7,
                        "shell.run",
                        {"command": [sys.executable, "-c", "print('COSTFREE_TEST_PASS')"]},
                    )
                )
            )
            if shell_result["returncode"] != 0:
                raise RuntimeError(f"shell.run failed: {shell_result}")
            if "COSTFREE_TEST_PASS" not in shell_result["stdout"]:
                raise RuntimeError(f"unexpected shell output: {shell_result}")

        finally:
            proc.terminate()
            proc.wait(timeout=5)

    print("COSTFREE-001 acceptance: PASS")


if __name__ == "__main__":
    run_acceptance()
