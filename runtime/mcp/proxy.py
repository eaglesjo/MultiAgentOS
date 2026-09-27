"""Provider-neutral MCP tool proxy."""
from core.contracts.mcp import MCPTool, MCPToolCall, MCPToolResult
from runtime.mcp.client import MCPClient

class MCPToolProxy:
    def __init__(self,clients:dict[str,MCPClient]): self.clients=clients
    def list_tools(self)->tuple[MCPTool,...]:
        tools=[]
        for client in self.clients.values(): tools.extend(client.list_tools())
        return tuple(tools)
    def call(self,request:MCPToolCall)->MCPToolResult:
        client=self.clients.get(request.server_id)
        if client is None: raise KeyError(f"MCP server not connected: {request.server_id}")
        if request.session_id and (client.session is None or client.session.id != request.session_id):
            raise KeyError(f"MCP session mismatch for {request.server_id}")
        return client.call_tool(request)
