"""Provider-neutral MCP client supporting stdio and Streamable HTTP."""
from __future__ import annotations
import json, os, subprocess, urllib.request, urllib.error, uuid
from dataclasses import dataclass
from typing import Any
from core.contracts.mcp import MCPServerSpec, MCPSession, MCPTool, MCPToolCall, MCPToolResult

class MCPError(RuntimeError): pass
class MCPProtocolError(MCPError): pass

@dataclass
class _StdioSession:
    process: subprocess.Popen[str]
    session: MCPSession
    next_id: int = 0

class MCPClient:
    """Connect to an external MCP server without embedding its implementation."""
    def __init__(self, server: MCPServerSpec, *, cwd: str | None = None, timeout: float = 30.0):
        self.server = server
        self.cwd = cwd
        self.timeout = timeout
        self._stdio: _StdioSession | None = None
        self._http_session: MCPSession | None = None
        self._next_id = 0

    @property
    def session(self) -> MCPSession | None:
        if self._stdio:
            return self._stdio.session
        return self._http_session

    def connect(self) -> MCPSession:
        if not self.server.enabled:
            raise MCPError(f"MCP server disabled: {self.server.id}")
        if self.server.transport == "stdio":
            if not self.server.command:
                raise MCPError(f"MCP server has no command: {self.server.id}")
            env = os.environ.copy()
            env.update(self.server.env)
            process = subprocess.Popen(
                [*self.server.command, *self.server.args], cwd=self.cwd, env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
            )
            session = MCPSession(str(uuid.uuid4()), self.server.id)
            self._stdio = _StdioSession(process, session)
            self._request_stdio("initialize", {
                "protocolVersion": session.protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "VYRELON", "version": "0.1"},
            })
            self._notify_stdio("notifications/initialized", {})
            return session
        if self.server.transport in {"streamable-http", "http", "sse"}:
            if not self.server.endpoint:
                raise MCPError(f"MCP server has no endpoint: {self.server.id}")
            result, headers = self._request_http("initialize", {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "VYRELON", "version": "0.1"},
            }, accept_session=True)
            session_id = headers.get("Mcp-Session-Id") or headers.get("mcp-session-id")
            if not session_id:
                session_id = str(uuid.uuid4())
            self._http_session = MCPSession(session_id, self.server.id,
                                            str(result.get("protocolVersion", "2025-03-26")))
            self._request_http("notifications/initialized", {}, notification=True)
            return self._http_session
        raise MCPError(f"Unsupported MCP transport: {self.server.transport}")

    def close(self) -> None:
        if self._stdio is not None:
            process = self._stdio.process
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=2)
                except subprocess.TimeoutExpired: process.kill()
            self._stdio = None
        self._http_session = None

    def list_tools(self) -> tuple[MCPTool, ...]:
        result = self._request("tools/list", {})
        return tuple(MCPTool(str(item["name"]), str(item.get("description", "")),
                             dict(item.get("inputSchema", {})), self.server.id)
                        for item in result.get("tools", []))

    def call_tool(self, call: MCPToolCall) -> MCPToolResult:
        if call.server_id != self.server.id:
            raise MCPError(f"Tool call targets {call.server_id}, not {self.server.id}")
        result = self._request("tools/call", {"name": call.tool_name, "arguments": call.arguments})
        return MCPToolResult(self.server.id, call.tool_name,
                             tuple(result.get("content", [])), bool(result.get("isError", False)), result)

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.server.transport == "stdio":
            return self._request_stdio(method, params)
        result, _ = self._request_http(method, params)
        return result

    def _request_stdio(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        s = self._stdio
        if s is None or s.process.stdin is None or s.process.stdout is None:
            raise MCPError("MCP client is not connected")
        s.next_id += 1
        request_id = s.next_id
        s.process.stdin.write(json.dumps({"jsonrpc":"2.0","id":request_id,"method":method,"params":params})+"\n")
        s.process.stdin.flush()
        while True:
            line=s.process.stdout.readline()
            if not line: raise MCPProtocolError(f"MCP server closed stdout while waiting for {method}")
            message=json.loads(line)
            if message.get("id") != request_id: continue
            if "error" in message: raise MCPProtocolError(str(message["error"]))
            return dict(message.get("result", {}))

    def _notify_stdio(self, method: str, params: dict[str, Any]) -> None:
        s=self._stdio
        if s is None or s.process.stdin is None: raise MCPError("MCP client is not connected")
        s.process.stdin.write(json.dumps({"jsonrpc":"2.0","method":method,"params":params})+"\n")
        s.process.stdin.flush()

    def _request_http(self, method: str, params: dict[str, Any], *,
                      notification: bool=False, accept_session: bool=False):
        if not self.server.endpoint: raise MCPError("MCP server has no endpoint")
        self._next_id += 1
        payload={"jsonrpc":"2.0","method":method,"params":params}
        if not notification: payload["id"]=self._next_id
        headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream", **self.server.headers}
        session=self._http_session
        if session: headers["Mcp-Session-Id"]=session.id
        request=urllib.request.Request(self.server.endpoint, data=json.dumps(payload).encode(),
                                       headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response_headers=dict(response.headers.items())
                if notification: return {}, response_headers
                body=response.read().decode()
        except urllib.error.HTTPError as exc:
            raise MCPProtocolError(f"MCP HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc
        except urllib.error.URLError as exc:
            raise MCPError(f"MCP HTTP transport error: {exc.reason}") from exc
        if "text/event-stream" in response_headers.get("Content-Type",""):
            data=self._last_sse_event(body)
            message=json.loads(data)
        else:
            message=json.loads(body)
        if "error" in message: raise MCPProtocolError(str(message["error"]))
        return dict(message.get("result", {})), response_headers

    @staticmethod
    def _last_sse_event(body: str) -> str:
        data=[]
        for line in body.splitlines():
            if line.startswith("data:"):
                data.append(line[5:].strip())
        if not data: raise MCPProtocolError("MCP SSE response contained no data event")
        return data[-1]
