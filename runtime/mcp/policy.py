"""MCP tool authorization and profile loading."""
from __future__ import annotations
import json
from pathlib import Path
from core.contracts.agent import AgentContract
from core.contracts.mcp import MCPTool, MCPToolProfile
from core.contracts.agent_execution_runtime import ToolSideEffect

class MCPAuthorizationError(PermissionError):
    pass

class MCPToolProfileLoader:
    def load(self, project_root: Path) -> tuple[MCPToolProfile, ...]:
        path = project_root / ".multiagentos" / "mcp-profiles.json"
        if not path.exists():
            return ()
        data = json.loads(path.read_text(encoding="utf-8"))
        result = []
        for profile_id, item in data.get("profiles", {}).items():
            result.append(MCPToolProfile(
                id=profile_id,
                server_ids=frozenset(item.get("servers", [])),
                allowed_tools=frozenset(item.get("tools", [])),
                denied_tools=frozenset(item.get("deny_tools", [])),
                required_permissions=frozenset(item.get("permissions", [])),
                allowed_side_effects=frozenset(ToolSideEffect(value) for value in item.get("side_effects", ["read"])),
                metadata=item.get("metadata", {}),
                tool_side_effects={key: ToolSideEffect(value) for key, value in item.get("tool_side_effects", {}).items()},
            ))
        return tuple(result)

class MCPToolAuthorizer:
    def __init__(self, profiles: tuple[MCPToolProfile, ...] = ()):
        self.profiles = {p.id: p for p in profiles}

    def authorize(self, agent: AgentContract, tool: MCPTool, profile_id: str | None = None) -> None:
        if profile_id:
            profile = self.profiles.get(profile_id)
            if profile is None:
                raise MCPAuthorizationError(f"MCP tool profile not found: {profile_id}")
            if not profile.allows(tool, agent.permissions):
                raise MCPAuthorizationError(f"MCP tool denied by profile '{profile_id}': {tool.server_id}:{tool.name}")
        elif agent.tools and tool.name not in agent.tools and f"{tool.server_id}:{tool.name}" not in agent.tools:
            raise MCPAuthorizationError(f"MCP tool not granted to agent: {tool.server_id}:{tool.name}")
        if tool.permissions and not tool.permissions.issubset(agent.permissions):
            missing = sorted(tool.permissions - agent.permissions)
            raise MCPAuthorizationError(f"MCP tool permission denied: {tool.server_id}:{tool.name}; missing={missing}")

    def filter_tools(self, agent: AgentContract, tools: tuple[MCPTool, ...], profile_id: str | None = None) -> tuple[MCPTool, ...]:
        return tuple(tool for tool in tools if self._allowed(agent, tool, profile_id))

    def _allowed(self, agent: AgentContract, tool: MCPTool, profile_id: str | None) -> bool:
        try:
            self.authorize(agent, tool, profile_id)
            return True
        except MCPAuthorizationError:
            return False
