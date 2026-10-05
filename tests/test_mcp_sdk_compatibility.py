"""Compatibility smoke test using the official MCP Python SDK v2 client."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from mcp.types import Request, RequestParams, Result
from pydantic import ConfigDict, Field, TypeAdapter
from typing import Literal


def test_official_mcp_sdk_stdio_compatibility() -> None:
    asyncio.run(_exercise_stdio_client())


async def _exercise_stdio_client() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "sdk-client.txt"
        target.write_text("mcp-sdk-compatibility", encoding="utf-8")

        server = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "multiagentos.cli",
                "mcp",
                "serve",
                "--path",
                str(root),
            ],
            cwd=str(Path.cwd()),
        )

        async with Client(server) as client:
            assert client.server_info is not None
            assert client.server_info.name == "Agent Execution Runtime"
            assert client.server_capabilities.tools is not None
            assert client.protocol_version

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
            assert getattr(result.content[0], "text", None) == "mcp-sdk-compatibility"


if __name__ == "__main__":
    test_official_mcp_sdk_stdio_compatibility()


class RecoveryParams(RequestParams):
    model_config = ConfigDict(populate_by_name=True)
    work_unit_id: str = Field(alias="workUnitId")


class RecoveryResult(Result):
    model_config = ConfigDict(populate_by_name=True)
    work_unit_id: str = Field(alias="workUnitId")
    disposition: str
    replayed: bool
    invocation_id: str | None = Field(default=None, alias="invocationId")
    idempotency_key: str | None = Field(default=None, alias="idempotencyKey")
    human_decision: str | None = Field(default=None, alias="humanDecision")


class RecoveryRequest(Request[RecoveryParams, Literal["runtime/recover"]]):
    method: Literal["runtime/recover"] = "runtime/recover"
    params: RecoveryParams


def test_official_mcp_sdk_low_level_custom_recovery() -> None:
    asyncio.run(_exercise_low_level_recovery())


async def _exercise_low_level_recovery() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / "sdk-low-level.txt"
        target.write_text("mcp-sdk-low-level", encoding="utf-8")

        server = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "multiagentos.cli",
                "mcp",
                "serve",
                "--path",
                str(root),
            ],
            cwd=str(Path.cwd()),
        )

        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialize = await session.initialize()
                assert initialize.server_info is not None
                assert initialize.server_info.name == "Agent Execution Runtime"

                result = await session.call_tool(
                    "filesystem.read",
                    {"path": target.name},
                )
                assert not result.is_error
                assert result.content
                assert getattr(result.content[0], "text", None) == "mcp-sdk-low-level"

                durable = root / ".multiagentos"
                state_files = list((durable / "state").glob("*.json"))
                assert len(state_files) == 1
                work_unit_id = __import__("json").loads(
                    state_files[0].read_text(encoding="utf-8")
                )["id"]

                request = RecoveryRequest(
                    params=RecoveryParams(work_unit_id=work_unit_id),
                )
                response = await session.send_request(
                    request,
                    RecoveryResult,
                )

                assert response.work_unit_id == work_unit_id
                assert response.disposition == "completed"
                assert response.replayed is False


if __name__ == "__main__":
    test_official_mcp_sdk_stdio_compatibility()
