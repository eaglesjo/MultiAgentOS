"""Crash-boundary launcher for Streamable HTTP MCP recovery tests."""

from __future__ import annotations

import sys
from pathlib import Path

from runtime.mcp.streamable_http import AgentExecutionRuntimeStreamableHTTPServer


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    port = int(sys.argv[2])
    allow_write = sys.argv[3] == "1"

    server = AgentExecutionRuntimeStreamableHTTPServer(
        root,
        allow_write=allow_write,
    )

    def crash_execute(*args, **kwargs):
        raise SystemExit(97)

    server.durable_bridge.tool_runtime.execute = crash_execute
    server.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
