"""Compatibility smoke test using the official MCP Python SDK v2 client."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters


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
