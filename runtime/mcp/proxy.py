"""Provider-neutral MCP tool proxy with agent authorization."""
from core.contracts.agent import AgentContract
from core.contracts.mcp import MCPTool, MCPToolCall, MCPToolResult
from runtime.mcp.client import MCPClient
from runtime.mcp.policy import MCPToolAuthorizer

class MCPToolProxy:
    def __init__(self, clients: dict[str, MCPClient], authorizer: MCPToolAuthorizer | None = None):
        self.clients = clients
        self.authorizer = authorizer or MCPToolAuthorizer()

    def list_tools(self, agent: AgentContract | None = None, profile_id: str | None = None) -> tuple[MCPTool, ...]:
        tools = []
        for client in self.clients.values():
            tools.extend(client.list_tools())
        result = tuple(tools)
        return result if agent is None else self.authorizer.filter_tools(agent, result, profile_id)

    def call(self, request: MCPToolCall, agent: AgentContract | None = None, profile_id: str | None = None) -> MCPToolResult:
        client = self.clients.get(request.server_id)
        if client is None:
            raise KeyError(f"MCP server not connected: {request.server_id}")
        if request.session_id and (client.session is None or client.session.id != request.session_id):
            raise KeyError(f"MCP session mismatch for {request.server_id}")
        if agent is not None:
            tool = next((item for item in client.list_tools() if item.name == request.tool_name), None)
            if tool is None:
                raise KeyError(f"MCP tool not found: {request.server_id}:{request.tool_name}")
            self.authorizer.authorize(agent, tool, profile_id)
        return client.call_tool(request)
