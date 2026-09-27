"""Persistent WorkUnit state store."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.work_unit import WorkStatus, WorkUnit
from core.contracts.vyrelon_runtime import SessionSpec, SessionState


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

    def exists(self, work_unit_id: str) -> bool:
        return (self.root / f"{work_unit_id}.json").exists()

    def list_ids(self) -> tuple[str, ...]:
        return tuple(sorted(path.stem for path in self.root.glob("*.json")))

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


class SessionStateStore:
    """Persist SessionState independently from WorkUnit state."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, state: SessionState) -> Path:
        path = self.root / f"{state.spec.id}.json"
        payload = {
            "spec": {
                "id": state.spec.id,
                "project_root": state.spec.project_root,
                "agent_id": state.spec.agent_id,
                "model_id": state.spec.model_id,
                "checkpoint_id": state.spec.checkpoint_id,
                "metadata": state.spec.metadata,
            },
            "work_unit_ids": state.work_unit_ids,
            "status": state.status,
            "metadata": state.metadata,
        }
        path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        return path

    def exists(self, session_id: str) -> bool:
        return (self.root / f"{session_id}.json").exists()

    def load(self, session_id: str) -> SessionState:
        data = json.loads((self.root / f"{session_id}.json").read_text(encoding="utf-8"))
        raw = data["spec"]
        spec = SessionSpec(
            id=raw["id"],
            project_root=raw["project_root"],
            agent_id=raw.get("agent_id"),
            model_id=raw.get("model_id"),
            checkpoint_id=raw.get("checkpoint_id"),
            metadata=dict(raw.get("metadata", {})),
        )
        return SessionState(
            spec=spec,
            work_unit_ids=list(data.get("work_unit_ids", [])),
            status=data.get("status", "active"),
            metadata=dict(data.get("metadata", {})),
        )
