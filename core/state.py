"""Persistent WorkUnit state store."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.checkpoint import WorkflowCheckpoint
from core.contracts.work_unit import WorkStatus, WorkUnit
from core.contracts.agent_execution_runtime import RuntimeEvent, SessionSpec, SessionState
from core.security import redact_sensitive


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



class RuntimeEventStore:
    """Append-only durable journal for Agent Execution Runtime events."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, event) -> Path:
        if event.work_unit_id is None:
            raise ValueError("runtime event requires work_unit_id")
        path = self.root / f"{event.work_unit_id}.jsonl"
        sequence = event.sequence if event.sequence is not None else self.next_sequence(event.work_unit_id)
        payload = {
            "kind": event.kind.value,
            "session_id": event.session_id,
            "work_unit_id": event.work_unit_id,
            "payload": redact_sensitive(event.payload),
            "sequence": sequence,
            "metadata": redact_sensitive(event.metadata),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        return path

    def load(self, work_unit_id: str) -> tuple[dict[str, object], ...]:
        path = self.root / f"{work_unit_id}.jsonl"
        if not path.exists():
            return ()
        return tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    def next_sequence(self, work_unit_id: str) -> int:
        events = self.load(work_unit_id)
        return (int(events[-1].get("sequence") or 0) + 1) if events else 1


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
