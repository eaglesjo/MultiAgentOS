"""Apply Agent Execution Runtime project bootstrap files."""

from __future__ import annotations

import json
from pathlib import Path

from agents.catalog import build_agent_catalog
from core.contracts.profile import DetectionResult
from runtime.execution_config import write_default_execution_config
from runtime.chat_config import write_default_chat_config


class ProjectInitializer:
    COMPONENTS = frozenset({"agent-execution-runtime", "multi-agent", "all"})

    def apply(
        self,
        project_root: Path,
        detections: tuple[DetectionResult, ...],
        component: str = "all",
    ) -> Path:
        if component not in self.COMPONENTS:
            raise ValueError(f"unsupported component: {component}")
        target = project_root / ".multiagentos"
        target.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "profiles": [
                {
                    "id": result.profile_id,
                    "confidence": result.confidence,
                    "evidence": list(result.evidence),
                }
                for result in detections
            ],
        }
        config = target / "profile.json"
        config.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (target / "components.json").write_text(
            json.dumps({"version": 1, "components": [component]}, indent=2) + "\n",
            encoding="utf-8",
        )

        # Project bootstrap is deliberately client-neutral: it prepares the
        # runtime contract without installing an IDE extension or mutating an
        # existing client-specific configuration.
        (target / "state").mkdir(exist_ok=True)
        (target / "checkpoints").mkdir(exist_ok=True)
        (target / "sessions").mkdir(exist_ok=True)
        (target / "mcp.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "transport": "streamable-http",
                    "endpoint": "http://127.0.0.1:8000/mcp",
                    "project_root": str(project_root.resolve()),
                    "allow_write": False,
                    "allow_process": False,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        agents_md = project_root / "AGENTS.md"
        if not agents_md.exists():
            agents_md.write_text(
                """# MultiAgentOS Project Runtime

This project is initialized for MultiAgentOS. The project-local runtime is the execution and governance boundary for coding-agent work.

## Runtime boundary

- Treat the repository and working tree as the source of truth.
- Use MultiAgentOS for project-scoped filesystem, patch, process, Git, and verification operations.
- Keep agent reasoning/client responsibilities separate from runtime execution authority.
- Do not introduce IDE-specific MultiAgentOS extensions or plugins as part of project runtime work.
- Preserve existing project-specific agent instructions and client configuration.

## Project profile

The detected platform/profile is recorded in `.multiagentos/profile.json`. Agent routing should use the detected project profile together with task domain, platform, technology, and governance constraints.

## Governance

Keep changes scoped to the requested work unit. Do not silently expand scope, discard user work, force-push, or perform release/publication actions without explicit approval.

## Local MCP

The project-local MCP contract is recorded in `.multiagentos/mcp.json`. The default endpoint is `http://127.0.0.1:8000/mcp`; write and process capabilities remain explicit opt-ins.
""",
                encoding="utf-8",
            )

        (target / ".gitignore").write_text(
            "state/\ncheckpoints/\nsessions/\n*.log\n",
            encoding="utf-8",
        )

        if component in {"agent-execution-runtime", "all"}:
            write_default_execution_config(project_root)
            write_default_chat_config(project_root)

        if component == "agent-execution-runtime":
            return config

        agents = build_agent_catalog(tuple(result.profile_id for result in detections))
        agent_payload = {
            "version": 1,
            "agents": [
                {
                    "id": agent.id,
                    "role": agent.role,
                    "kind": agent.kind,
                    "capabilities": sorted(agent.capabilities),
                    "tools": sorted(agent.tools),
                    "permissions": sorted(agent.permissions),
                    "models": list(agent.model_ids),
                }
                for agent in agents
            ],
        }
        (target / "agents.json").write_text(
            json.dumps(agent_payload, indent=2) + "\n", encoding="utf-8"
        )
        return config
