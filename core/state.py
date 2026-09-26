"""Persistent WorkUnit state store."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.work_unit import WorkStatus, WorkUnit


class WorkStateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, work_unit: WorkUnit) -> Path:
        path = self.root / f"{work_unit.id}.json"
        payload = {
            "id": work_unit.id,
            "objective": work_unit.objective,
            "status": work_unit.status.value,
            "inputs": work_unit.inputs,
            "artifacts": work_unit.artifacts,
            "assigned_agents": work_unit.assigned_agents,
            "metadata": work_unit.metadata,
        }
        path.write_text(
            json.dumps(payload, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        return path

    def load(self, work_unit_id: str) -> WorkUnit:
        path = self.root / f"{work_unit_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return WorkUnit(
            id=data["id"],
            objective=data["objective"],
            status=WorkStatus(data["status"]),
            inputs=dict(data.get("inputs", {})),
            artifacts=list(data.get("artifacts", [])),
            assigned_agents=list(data.get("assigned_agents", [])),
            metadata=dict(data.get("metadata", {})),
        )
