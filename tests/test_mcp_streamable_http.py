"""Official MCP SDK Streamable HTTP compatibility and policy tests."""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from mcp import Client
from mcp.types import Request
from pydantic import TypeAdapter


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(
    root: Path,
    port: int,
    *,
    allow_write: bool = False,
) -> subprocess.Popen[str]:
    args = [
        sys.executable,
        "-m",
        "multiagentos.cli",
        "mcp",
        "serve-http",
        "--path",
        str(root),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    if allow_write:
        args.append("--allow-write")
    return subprocess.Popen(
        args,
        cwd=str(Path.cwd()),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_http(port: int, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr else ""
            raise AssertionError(f"HTTP MCP server exited early: {stderr}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError("timed out waiting for Streamable HTTP MCP server")


def _stop_server(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def test_official_mcp_sdk_streamable_http_read_and_policy() -> None:
    asyncio.run(_exercise_http_read_and_policy())


async def _exercise_http_read_and_policy() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "http-client.txt"
        target.write_text("streamable-http", encoding="utf-8")
        port = _free_port()
        process = _start_server(root, port)
        try:
            _wait_for_http(port, process)
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                assert client.server_info is not None
                assert client.server_info.name == "Agent Execution Runtime"
                assert client.server_capabilities.tools is not None

                tools = await client.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                assert "filesystem.read" in tool_names
                assert "filesystem.write" not in tool_names

                result = await client.call_tool(
                    "filesystem.read",
                    {"path": target.name},
                )
                assert not result.is_error
                assert result.content
                assert getattr(result.content[0], "text", None) == "streamable-http"
        finally:
            _stop_server(process)


def test_official_mcp_sdk_streamable_http_write_requires_explicit_opt_in() -> None:
    asyncio.run(_exercise_http_write_policy())


async def _exercise_http_write_policy() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "write.txt"
        target.write_text("before", encoding="utf-8")
        port = _free_port()
        process = _start_server(root, port, allow_write=True)
        try:
            _wait_for_http(port, process)
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                tools = await client.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                assert "filesystem.write" in tool_names

                result = await client.call_tool(
                    "filesystem.write",
                    {"path": target.name, "content": "after"},
                )
                assert not result.is_error
                assert target.read_text(encoding="utf-8") == "after"
        finally:
            _stop_server(process)


def test_official_mcp_sdk_streamable_http_recovery_method() -> None:
    asyncio.run(_exercise_http_recovery_method())


async def _exercise_http_recovery_method() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "recovery.txt"
        target.write_text("http-recovery", encoding="utf-8")
        port = _free_port()
        process = _start_server(root, port)
        try:
            _wait_for_http(port, process)
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                result = await client.call_tool(
                    "filesystem.read",
                    {"path": target.name},
                )
                assert not result.is_error

                state_files = list((root / ".multiagentos" / "state").glob("*.json"))
                assert len(state_files) == 1
                work_unit_id = json.loads(
                    state_files[0].read_text(encoding="utf-8")
                )["id"]

                response = await client.session.send_request(
                    Request(
                        method="runtime/recover",
                        params={"workUnitId": work_unit_id},
                    ),
                    TypeAdapter(dict[str, object]),
                )
                assert response["workUnitId"] == work_unit_id
                assert response["disposition"] == "completed"
                assert response["replayed"] is False
        finally:
            _stop_server(process)


if __name__ == "__main__":
    test_official_mcp_sdk_streamable_http_read_and_policy()
