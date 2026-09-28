"""Apply VYRELON project bootstrap files."""

from __future__ import annotations

import json
from pathlib import Path

from agents.catalog import build_agent_catalog
from core.contracts.profile import DetectionResult
from runtime.execution_config import write_default_execution_config
from runtime.chat_config import write_default_chat_config


class ProjectInitializer:
    COMPONENTS = frozenset({"vyrelon", "multi-agent", "all"})

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

        if component in {"vyrelon", "all"}:
            write_default_execution_config(project_root)
            write_default_chat_config(project_root)

        if component == "vyrelon":
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
