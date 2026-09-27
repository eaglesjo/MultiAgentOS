"""Declarative MCP server configuration."""
from __future__ import annotations
import json
from pathlib import Path
from core.contracts.mcp import MCPServerSpec

class MCPConfigLoader:
    def load(self, project_root: Path) -> list[MCPServerSpec]:
        path = project_root / ".multiagentos" / "mcp.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        servers = data.get("servers", data.get("mcpServers", {}))
        result = []
        for server_id, raw in servers.items():
            command = raw.get("command")
            if isinstance(command, str):
                command = (command,)
            else:
                command = tuple(command or ())
            args = tuple(str(x) for x in raw.get("args", ()))
            result.append(MCPServerSpec(
                id=server_id,
                command=tuple(command),
                args=args,
                env={str(k): str(v) for k,v in raw.get("env", {}).items()},
                transport=str(raw.get("transport", "stdio")),
                endpoint=raw.get("url", raw.get("endpoint")),
                headers={str(k): str(v) for k,v in raw.get("headers", {}).items()},
                enabled=bool(raw.get("enabled", True)),
                metadata=dict(raw.get("metadata", {})),
            ))
        return result
