"""Canonical MCP server entry point for the Agent Execution Runtime.

The legacy runtime.mcp.server.AgentExecutionRuntimeMCPServer remains available for compatibility.
"""

from runtime.mcp.server import AgentExecutionRuntimeMCPServer

__all__ = ["AgentExecutionRuntimeMCPServer"]
