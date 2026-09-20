"""Apply VYRELON project bootstrap files."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.profile import DetectionResult
from agents.catalog import build_agent_catalog
from installer.components import resolve_installation


class ProjectInitializer:
    def apply(
        self,
        project_root: Path,
        detections: tuple[DetectionResult, ...],
        component: str = "all",
    ) -> Path:
        installation = resolve_installation(component)
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
            json.dumps(installation.as_payload(), indent=2) + "\n",
            encoding="utf-8",
        )

        if installation.has_multi_agent:
            agents = build_agent_catalog(
                tuple(result.profile_id for result in detections)
            )
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
                json.dumps(agent_payload, indent=2) + "\n",
                encoding="utf-8",
            )

        return config
