"""Provider-neutral MCP runtime contracts for VYRELON."""
from __future__ import annotations
from dataclasses import dataclass, field
from core.contracts.vyrelon_runtime import ToolSideEffect

@dataclass(frozen=True)
class MCPServerSpec:
    id: str
    command: tuple[str, ...] = ()
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"
    endpoint: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    metadata: dict[str, object] = field(default_factory=dict)
    source: str = "built-in"
    cost_policy: str = "no_external_billing"
    requires_explicit_enable: bool = False

@dataclass(frozen=True)
class MCPSession:
    id: str
    server_id: str
    protocol_version: str = "2025-03-26"
    metadata: dict[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str = ""
    input_schema: dict[str, object] = field(default_factory=dict)
    server_id: str = ""
    side_effect: ToolSideEffect = ToolSideEffect.READ
    permissions: frozenset[str] = frozenset()
    metadata: dict[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class MCPToolCall:
    server_id: str
    tool_name: str
    arguments: dict[str, object] = field(default_factory=dict)
    session_id: str | None = None

@dataclass(frozen=True)
class MCPToolResult:
    server_id: str
    tool_name: str
    content: tuple[object, ...] = ()
    is_error: bool = False
    raw: object = None

@dataclass(frozen=True)
class MCPToolProfile:
    """Agent-facing MCP access policy."""
    id: str
    server_ids: frozenset[str] = frozenset()
    allowed_tools: frozenset[str] = frozenset()
    denied_tools: frozenset[str] = frozenset()
    required_permissions: frozenset[str] = frozenset()
    allowed_side_effects: frozenset[ToolSideEffect] = frozenset({ToolSideEffect.READ})
    metadata: dict[str, object] = field(default_factory=dict)
    tool_side_effects: dict[str, ToolSideEffect] = field(default_factory=dict)

    def allows(self, tool: MCPTool, permissions: frozenset[str] = frozenset()) -> bool:
        if self.server_ids and tool.server_id not in self.server_ids:
            return False
        qualified = f"{tool.server_id}:{tool.name}"
        if qualified in self.denied_tools or tool.name in self.denied_tools:
            return False
        if self.allowed_tools and qualified not in self.allowed_tools and tool.name not in self.allowed_tools:
            return False
        effective_side_effect = self.tool_side_effects.get(qualified, self.tool_side_effects.get(tool.name, tool.side_effect))
        if effective_side_effect not in self.allowed_side_effects:
            return False
        return self.required_permissions.issubset(permissions) and tool.permissions.issubset(permissions)
