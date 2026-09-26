"""Persistent checkpoint storage for VYRELON WorkUnits."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.checkpoint import WorkflowCheckpoint
from core.contracts.work_unit import WorkStatus, WorkUnit


class WorkStateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.checkpoint_root = self.root.parent / "checkpoints"
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)

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

    def save_checkpoint(self, checkpoint: WorkflowCheckpoint) -> Path:
        """Persist a durable checkpoint independently of transient model output."""
        checkpoint.validate()
        path = self.checkpoint_root / f"{checkpoint.work_unit_id}.json"
        path.write_text(
            json.dumps(checkpoint.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def load_checkpoint(self, work_unit_id: str) -> WorkflowCheckpoint:
        """Load the latest durable checkpoint for a WorkUnit."""
        path = self.checkpoint_root / f"{work_unit_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return WorkflowCheckpoint.from_dict(data)

    def checkpoint(
        self,
        work_unit: WorkUnit,
        *,
        workflow: str,
        stage: str,
        sequence: int = 0,
        next_action: str | None = None,
        agent_ids: tuple[str, ...] = (),
        model_ids: tuple[str, ...] = (),
        resumable: bool = True,
        metadata: dict[str, object] | None = None,
    ) -> WorkflowCheckpoint:
        """Persist WorkUnit state and a normalized checkpoint atomically at the API level."""
        self.save(work_unit)
        checkpoint = WorkflowCheckpoint(
            schema_version=1,
            work_unit_id=work_unit.id,
            workflow=workflow,
            status=work_unit.status.value,
            stage=stage,
            sequence=sequence,
            next_action=next_action,
            agent_ids=agent_ids,
            model_ids=model_ids,
            artifact_ids=tuple(work_unit.artifacts),
            findings=tuple(
                str(value) for value in work_unit.metadata.get("findings", ())
            ),
            resumable=resumable,
            metadata=dict(metadata or {}),
        )
        self.save_checkpoint(checkpoint)
        return checkpoint
