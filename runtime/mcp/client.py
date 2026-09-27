"""Minimal MCP client supporting stdio JSON-RPC 2.0 servers."""
from __future__ import annotations
import json, os, subprocess
from dataclasses import dataclass
from typing import Any
from core.contracts.mcp import MCPServerSpec, MCPTool, MCPToolCall, MCPToolResult

class MCPError(RuntimeError): pass
class MCPProtocolError(MCPError): pass

@dataclass
class _StdioSession:
    process: subprocess.Popen[str]
    next_id: int = 0

class MCPClient:
    """Connect to external MCP servers without making them part of VYRELON core."""
    def __init__(self, server: MCPServerSpec, *, cwd: str | None = None):
        self.server = server
        self.cwd = cwd
        self._stdio: _StdioSession | None = None

    def connect(self) -> None:
        if not self.server.enabled:
            raise MCPError(f"MCP server disabled: {self.server.id}")
        if self.server.transport != "stdio":
            raise MCPError(f"Unsupported MCP transport: {self.server.transport}")
        if not self.server.command:
            raise MCPError(f"MCP server has no command: {self.server.id}")
        env = os.environ.copy()
        env.update(self.server.env)
        process = subprocess.Popen(
            [*self.server.command, *self.server.args],
            cwd=self.cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._stdio = _StdioSession(process)
        self._request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "VYRELON", "version": "0.1"},
        })
        self._notify("notifications/initialized", {})

    def close(self) -> None:
        if self._stdio is not None:
            process = self._stdio.process
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=2)
                except subprocess.TimeoutExpired: process.kill()
            self._stdio = None

    def list_tools(self) -> tuple[MCPTool, ...]:
        result = self._request("tools/list", {})
        tools = result.get("tools", [])
        return tuple(
            MCPTool(
                name=str(item["name"]),
                description=str(item.get("description", "")),
                input_schema=dict(item.get("inputSchema", {})),
                server_id=self.server.id,
            )
            for item in tools
        )

    def call_tool(self, call: MCPToolCall) -> MCPToolResult:
        if call.server_id != self.server.id:
            raise MCPError(f"Tool call targets {call.server_id}, not {self.server.id}")
        result = self._request("tools/call", {
            "name": call.tool_name,
            "arguments": call.arguments,
        })
        return MCPToolResult(
            server_id=self.server.id,
            tool_name=call.tool_name,
            content=tuple(result.get("content", [])),
            is_error=bool(result.get("isError", False)),
            raw=result,
        )

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        session = self._stdio
        if session is None or session.process.stdin is None or session.process.stdout is None:
            raise MCPError("MCP client is not connected")
        session.next_id += 1
        request_id = session.next_id
        payload = json.dumps({"jsonrpc":"2.0","id":request_id,"method":method,"params":params})
        session.process.stdin.write(payload + "\n")
        session.process.stdin.flush()
        while True:
            line = session.process.stdout.readline()
            if not line:
                raise MCPProtocolError(f"MCP server closed stdout while waiting for {method}")
            message = json.loads(line)
            if "id" not in message:
                continue
            if message["id"] != request_id:
                continue
            if "error" in message:
                raise MCPProtocolError(str(message["error"]))
            return dict(message.get("result", {}))

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        session = self._stdio
        if session is None or session.process.stdin is None:
            raise MCPError("MCP client is not connected")
        session.process.stdin.write(json.dumps({
            "jsonrpc":"2.0","method":method,"params":params
        }) + "\n")
        session.process.stdin.flush()
