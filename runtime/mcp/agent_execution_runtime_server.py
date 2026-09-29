"""Canonical MCP server entry point for the Agent Execution Runtime.

The legacy runtime.mcp.server.VYRELONMCPServer remains available for compatibility.
"""

from runtime.mcp.server import VYRELONMCPServer


class AgentExecutionRuntimeMCPServer(VYRELONMCPServer):
    """Canonical public name for the local Agent Execution Runtime MCP server."""

    def handle(self, message: dict[str, object]) -> dict[str, object] | None:
        response = super().handle(message)
        if (
            isinstance(response, dict)
            and isinstance(response.get("result"), dict)
            and isinstance(response["result"].get("serverInfo"), dict)
        ):
            response["result"]["serverInfo"]["name"] = "Agent Execution Runtime"
        return response


__all__ = ["AgentExecutionRuntimeMCPServer"]
