"""MCP stdio server exposing the Agent Execution Runtime local tool surface."""

from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from runtime.builtin_tools import BuiltinToolBindings
from runtime.policy import ExecutionPolicy
from runtime.tool_calling import ToolRuntime
from core.contracts.agent_execution_runtime import ToolRequest


def _server_version() -> str:
    try:
        return version("multiagentos")
    except PackageNotFoundError:
        return "0.0.0-dev"


class AgentExecutionRuntimeMCPServer:
    """Canonical stdio MCP server for Secure MCP Tunnel's mcp-command."""

    PROTOCOL_VERSION = "2025-03-26"
    SERVER_NAME = "Agent Execution Runtime"

    def __init__(
        self,
        project_root: Path,
        *,
        allow_write: bool = False,
        allow_process: bool = False,
    ) -> None:
        self.project_root = project_root.resolve()
        self.runtime = ToolRuntime(
            ExecutionPolicy(
                allow_process=allow_process,
                allow_filesystem_write=allow_write,
            )
        )
        BuiltinToolBindings(str(self.project_root), self.runtime)

    def _visible_tools(self) -> list[dict[str, object]]:
        result = []
        for spec in self.runtime.specs():
            capability = {
                "write": "filesystem.write",
                "execute": "process",
            }.get(spec.side_effect.value)
            if capability and not self.runtime.policy.permits(capability):
                continue
            result.append(
                {
                    "name": spec.id,
                    "description": spec.description,
                    "inputSchema": spec.input_schema,
                }
            )
        return result

    def _call(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        result = self.runtime.execute(
            ToolRequest(name, arguments),
            granted_permissions=frozenset(
                {
                    "filesystem.write"
                    if self.runtime.policy.allow_filesystem_write
                    else "",
                    "process" if self.runtime.policy.allow_process else "",
                }
            )
            - {""},
            approved=True,
        )
        if result.ok:
            output = result.output
            text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, default=str)
            return {"content": [{"type": "text", "text": text}], "isError": False}
        return {"content": [{"type": "text", "text": result.error or "tool execution failed"}], "isError": True}

    def handle(self, message: dict[str, object]) -> dict[str, object] | None:
        method = message.get("method")
        request_id = message.get("id")

        if method == "notifications/initialized":
            return None

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.SERVER_NAME, "version": _server_version()},
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": self._visible_tools()},
            }

        if method == "tools/call":
            params = message.get("params")
            if not isinstance(params, dict):
                return self._error(request_id, -32602, "params must be an object")
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not isinstance(name, str) or not name:
                return self._error(request_id, -32602, "tool name is required")
            if not isinstance(arguments, dict):
                return self._error(request_id, -32602, "tool arguments must be an object")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": self._call(name, dict(arguments)),
            }

        return self._error(request_id, -32601, f"method not found: {method}")

    @staticmethod
    def _error(request_id: object, code: int, message: str) -> dict[str, object]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def serve_forever(self, stdin=None, stdout=None) -> None:
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("JSON-RPC message must be an object")
                response = self.handle(message)
            except Exception as exc:
                response = self._error(None, -32603, str(exc))
            if response is not None:
                stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                stdout.flush()


class VYRELONMCPServer(AgentExecutionRuntimeMCPServer):
    """Legacy compatibility facade for the canonical MCP server."""

    SERVER_NAME = "VYRELON"


__all__ = ["AgentExecutionRuntimeMCPServer", "VYRELONMCPServer"]
