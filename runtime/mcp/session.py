"""MCP session registry."""
from runtime.mcp.client import MCPClient, MCPError
from core.contracts.mcp import MCPSession

class MCPSessionRegistry:
    def __init__(self): self._clients={}
    def add(self,client:MCPClient)->MCPSession:
        if client.session is None: raise MCPError("MCP client is not connected")
        self._clients[client.session.id]=client
        return client.session
    def get(self,session_id:str)->MCPClient:
        if session_id not in self._clients: raise MCPError(f"MCP session not found: {session_id}")
        return self._clients[session_id]
    def close(self,session_id:str)->None:
        client=self._clients.pop(session_id,None)
        if client: client.close()
    def close_all(self)->None:
        for client in list(self._clients.values()): client.close()
        self._clients.clear()
