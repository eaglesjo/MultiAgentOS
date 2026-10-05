"""Provider-neutral MCP tool proxy with execution authorization."""

from core.contracts.agent import AgentContract
from core.contracts.execution_decision import ExecutionDecision
from core.contracts.mcp import MCPTool, MCPToolCall, MCPToolResult
from runtime.mcp.client import MCPClient
from runtime.mcp.policy import MCPToolAuthorizer


class MCPToolProxy:
    def __init__(
        self,
        clients: dict[str, MCPClient],
        authorizer: MCPToolAuthorizer | None = None,
    ):
        self.clients = clients
        self.authorizer = authorizer or MCPToolAuthorizer()

    def list_tools(
        self,
        agent: AgentContract | None = None,
        profile_id: str | None = None,
    ) -> tuple[MCPTool, ...]:
        tools = []
        for client in self.clients.values():
            tools.extend(client.list_tools())
        result = tuple(tools)
        return (
            result
            if agent is None
            else self.authorizer.filter_tools(agent, result, profile_id)
        )

    def call(
        self,
        request: MCPToolCall,
        agent: AgentContract | None = None,
        profile_id: str | None = None,
        *,
        decision: ExecutionDecision | None = None,
    ) -> MCPToolResult:
        """Call an MCP tool, enforcing the execution decision when supplied."""
        client = self.clients.get(request.server_id)
        if client is None:
            raise KeyError(f"MCP server not connected: {request.server_id}")
        if request.session_id and (
            client.session is None or client.session.id != request.session_id
        ):
            raise KeyError(f"MCP session mismatch for {request.server_id}")

        authorization_metadata: dict[str, object] | None = None
        if agent is not None:
            tool = next(
                (item for item in client.list_tools() if item.name == request.tool_name),
                None,
            )
            if tool is None:
                raise KeyError(
                    f"MCP tool not found: {request.server_id}:{request.tool_name}"
                )

            if decision is not None:
                authorization = self.authorizer.authorize_execution(
                    decision=decision,
                    agent=agent,
                    tool=tool,
                    profile_id=profile_id,
                )
                authorization_metadata = authorization.to_metadata()
            else:
                self.authorizer.authorize(agent, tool, profile_id)

        result = client.call_tool(request)
        if authorization_metadata is None:
            return result
        return MCPToolResult(
            server_id=result.server_id,
            tool_name=result.tool_name,
            content=result.content,
            is_error=result.is_error,
            raw=result.raw,
            metadata={"tool_authorization": authorization_metadata},
        )
