"""Official MCP SDK Streamable HTTP compatibility and policy tests."""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Literal

from mcp import Client
import mcp.types as types
from pydantic import ConfigDict, Field


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
                assert client.protocol_version == "2026-07-28"
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



def test_streamable_http_modern_server_discover_wire_contract() -> None:
    asyncio.run(_exercise_modern_server_discover())


async def _exercise_modern_server_discover() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        port = _free_port()
        process = _start_server(root, port)
        try:
            _wait_for_http(port, process)
            payload = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "server/discover",
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                            "io.modelcontextprotocol/clientInfo": {
                                "name": "MultiAgentOS acceptance test",
                                "version": "0.0.0",
                            },
                        }
                    },
                }
            ).encode("utf-8")
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/mcp",
                data=payload,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                    "MCP-Protocol-Version": "2026-07-28",
                    "Mcp-Method": "server/discover",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read().decode("utf-8")
                assert response.status == 200
                assert "serverInfo" in body or "io.modelcontextprotocol/serverInfo" in body
                assert "Agent Execution Runtime" in body
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


class RecoveryParams(types.RequestParams):
    model_config = ConfigDict(populate_by_name=True)
    work_unit_id: str = Field(alias="workUnitId")
    session_id: str | None = Field(default=None, alias="sessionId")
    human_decision: str | None = Field(default=None, alias="humanDecision")
    notes: str = ""


class RecoveryResult(types.Result):
    model_config = ConfigDict(populate_by_name=True)
    work_unit_id: str = Field(alias="workUnitId")
    disposition: str
    replayed: bool
    invocation_id: str | None = Field(default=None, alias="invocationId")
    idempotency_key: str | None = Field(default=None, alias="idempotencyKey")
    human_decision: str | None = Field(default=None, alias="humanDecision")


class RecoveryRequest(types.Request[RecoveryParams, Literal["runtime/recover"]]):
    method: Literal["runtime/recover"] = "runtime/recover"
    params: RecoveryParams


def _start_crash_server(root: Path, port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "tests/mcp_streamable_http_crash_launcher.py",
            str(root),
            str(port),
            "1",
        ],
        cwd=str(Path.cwd()),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_streamable_http_write_crash_requires_and_accepts_human_recovery() -> None:
    asyncio.run(_exercise_http_write_crash_recovery())


async def _exercise_http_write_crash_recovery() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "http-side-effect.txt"
        target.write_text("before", encoding="utf-8")

        crash_port = _free_port()
        crashed = _start_crash_server(root, crash_port)
        try:
            _wait_for_http(crash_port, crashed)
            try:
                async with Client(f"http://127.0.0.1:{crash_port}/mcp") as client:
                    await client.call_tool(
                        "filesystem.write",
                        {"path": target.name, "content": "after"},
                    )
            except Exception:
                pass
            crashed.wait(timeout=5)
            assert crashed.returncode == 97
        finally:
            if crashed.poll() is None:
                _stop_server(crashed)

        assert target.read_text(encoding="utf-8") == "before"
        state_files = list((root / ".multiagentos" / "state").glob("*.json"))
        assert len(state_files) == 1
        work_unit_id = json.loads(
            state_files[0].read_text(encoding="utf-8")
        )["id"]

        port = _free_port()
        process = _start_server(root, port, allow_write=True)
        try:
            _wait_for_http(port, process)
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                rejected = await client.session.send_request(
                    RecoveryRequest(
                        params=RecoveryParams(work_unit_id=work_unit_id),
                    ),
                    RecoveryResult,
                )
                assert rejected.disposition == "review_required"
                assert rejected.replayed is False

                approved = await client.session.send_request(
                    RecoveryRequest(
                        params=RecoveryParams(
                            work_unit_id=work_unit_id,
                            human_decision="approve",
                            notes="Approve the interrupted filesystem write after human review.",
                        ),
                    ),
                    RecoveryResult,
                )
                assert approved.disposition == "completed"
                assert approved.replayed is True

                verify = await client.call_tool(
                    "filesystem.read",
                    {"path": target.name},
                )
                assert not verify.is_error
                assert getattr(verify.content[0], "text", None) == "after"
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
                    RecoveryRequest(
                        params=RecoveryParams(work_unit_id=work_unit_id),
                    ),
                    RecoveryResult,
                )
                assert response.work_unit_id == work_unit_id
                assert response.disposition == "completed"
                assert response.replayed is False
        finally:
            _stop_server(process)


if __name__ == "__main__":
    test_official_mcp_sdk_streamable_http_read_and_policy()
