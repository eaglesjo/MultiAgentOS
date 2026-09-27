"""Provider-neutral MCP runtime contracts for VYRELON."""
from __future__ import annotations
from dataclasses import dataclass, field

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

@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str = ""
    input_schema: dict[str, object] = field(default_factory=dict)
    server_id: str = ""

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
