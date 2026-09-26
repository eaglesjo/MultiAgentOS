"""Project-level VYRELON installation and workflow status."""

from __future__ import annotations

import json
from pathlib import Path


def project_status(project_root: Path) -> dict[str, object]:
    """Return a read-only summary of installed components and durable state."""
    root = project_root.expanduser().resolve()
    target = root / ".multiagentos"
    result: dict[str, object] = {
        "project_root": str(root),
        "initialized": target.is_dir(),
        "components": [],
        "profiles": [],
        "agents": [],
        "work_units": [],
        "checkpoints": [],
    }
    if not target.is_dir():
        return result

    components_path = target / "components.json"
    if components_path.exists():
        data = json.loads(components_path.read_text(encoding="utf-8"))
        result["components"] = list(data.get("components", []))

    profile_path = target / "profile.json"
    if profile_path.exists():
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        result["profiles"] = list(data.get("profiles", []))

    agents_path = target / "agents.json"
    if agents_path.exists():
        data = json.loads(agents_path.read_text(encoding="utf-8"))
        result["agents"] = [agent.get("id", "") for agent in data.get("agents", [])]

    state_root = target / "state"
    if state_root.is_dir():
        for path in sorted(state_root.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            result["work_units"].append(
                {
                    "id": data.get("id", path.stem),
                    "objective": data.get("objective", ""),
                    "status": data.get("status", ""),
                }
            )

    checkpoint_root = target / "checkpoints"
    if checkpoint_root.is_dir():
        for path in sorted(checkpoint_root.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            result["checkpoints"].append(
                {
                    "work_unit_id": data.get("work_unit_id", path.stem),
                    "workflow": data.get("workflow", ""),
                    "stage": data.get("stage", ""),
                    "status": data.get("status", ""),
                    "next_action": data.get("next_action"),
                    "sequence": data.get("sequence", 0),
                    "resumable": bool(data.get("resumable", True)),
                }
            )

    return result
