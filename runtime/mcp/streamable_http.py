"""Official MCP SDK Streamable HTTP server for the Agent Execution Runtime."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from runtime.builtin_tools import BuiltinToolBindings
from runtime.mcp.durable_bridge import MCPDurableExecutionBridge
from runtime.policy import ExecutionPolicy
from runtime.tool_calling import ToolRuntime


def _server_version() -> str:
    try:
        return version("multiagentos")
    except PackageNotFoundError:
        return "0.0.0-dev"


class AgentExecutionRuntimeStreamableHTTPServer:
    """Official MCP SDK low-level server using Streamable HTTP."""

    SERVER_NAME = "Agent Execution Runtime"

    def __init__(
        self,
        project_root: Path,
        *,
        allow_write: bool = False,
        allow_process: bool = False,
        allowed_hosts: tuple[str, ...] | None = None,
        allowed_origins: tuple[str, ...] | None = None,
    ) -> None:
        try:
            from mcp.server import Server
            from mcp.types import RequestParams, Result
            from pydantic import ConfigDict, Field
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                'Streamable HTTP requires the optional MCP SDK dependency. '
                'Install with: pip install "multiagentos[mcp-http]"'
            ) from exc

        self.project_root = project_root.resolve()
        self.allowed_hosts = tuple(allowed_hosts or ())
        self.allowed_origins = tuple(allowed_origins or ())
        self.runtime = ToolRuntime(
            ExecutionPolicy(
                allow_process=allow_process,
                allow_filesystem_write=allow_write,
            )
        )
        BuiltinToolBindings(str(self.project_root), self.runtime)
        self.durable_bridge = MCPDurableExecutionBridge(
            self.project_root,
            self.runtime,
        )

        class RecoveryRequestParams(RequestParams):
            model_config = ConfigDict(populate_by_name=True)
            work_unit_id: str = Field(alias="workUnitId")
            session_id: str | None = Field(default=None, alias="sessionId")
            human_decision: str | None = Field(default=None, alias="humanDecision")
            notes: str = ""

        class RecoveryResult(Result):
            model_config = ConfigDict(populate_by_name=True)
            work_unit_id: str = Field(alias="workUnitId")
            disposition: str
            replayed: bool
            invocation_id: str | None = Field(default=None, alias="invocationId")
            idempotency_key: str | None = Field(default=None, alias="idempotencyKey")
            human_decision: str | None = Field(default=None, alias="humanDecision")

        self._RecoveryResult = RecoveryResult
        self._server = Server(
            self.SERVER_NAME,
            version=_server_version(),
            on_list_tools=self._list_tools,
            on_call_tool=self._call_tool,
        )
        self._server.add_request_handler(
            "runtime/recover",
            RecoveryRequestParams,
            self._recover,
        )

    def _visible_tools(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
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

    async def _list_tools(self, ctx, params):
        from mcp.types import ListToolsResult, Tool

        return ListToolsResult(
            tools=[
                Tool(
                    name=str(tool["name"]),
                    description=str(tool["description"]),
                    input_schema=dict(tool["inputSchema"]),
                )
                for tool in self._visible_tools()
            ]
        )

    async def _call_tool(self, ctx, params):
        from mcp.types import CallToolResult, TextContent

        arguments = dict(params.arguments or {})
        try:
            result = self.durable_bridge.call(params.name, arguments)
        except Exception as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=str(exc))],
                is_error=True,
            )

        if result.ok:
            output = result.output
            text = (
                output
                if isinstance(output, str)
                else json.dumps(output, ensure_ascii=False, default=str)
            )
            return CallToolResult(
                content=[TextContent(type="text", text=text)],
                is_error=False,
            )

        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=result.error or "tool execution failed",
                )
            ],
            is_error=True,
        )

    async def _recover(self, ctx, params):
        result = self.durable_bridge.recover(
            params.work_unit_id,
            session_id=params.session_id,
            human_decision=params.human_decision,
            notes=params.notes,
        )
        return self._RecoveryResult(
            work_unit_id=result["work_unit_id"],
            disposition=result["disposition"],
            replayed=result["replayed"],
            invocation_id=result.get("invocation_id"),
            idempotency_key=result.get("idempotency_key"),
            human_decision=result.get("human_decision"),
        )

    def app(self, *, host: str = "127.0.0.1"):
        """Build the official SDK Streamable HTTP ASGI application."""
        return self._server.streamable_http_app(
            streamable_http_path="/mcp",
            host="127.0.0.1",
            json_response=True,
        )

    def run(self, *, host: str = "127.0.0.1", port: int = 8000) -> None:
        try:
            import uvicorn
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                'Streamable HTTP requires uvicorn. '
                'Install with: pip install "multiagentos[mcp-http]"'
            ) from exc

        app = self._server.streamable_http_app(
            streamable_http_path="/mcp",
            host=host,
            json_response=True,
        )
        uvicorn.run(app, host=host, port=port, log_level="info")


__all__ = ["AgentExecutionRuntimeStreamableHTTPServer"]
