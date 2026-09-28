"""Durable checkpoint state for resumable VYRELON workflows."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkflowCheckpoint:
    """Serializable checkpoint describing the last durable workflow boundary."""

    schema_version: int
    work_unit_id: str
    workflow: str
    status: str
    stage: str
    sequence: int = 0
    next_action: str | None = None
    agent_ids: tuple[str, ...] = ()
    model_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    resumable: bool = True
    metadata: dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if self.schema_version < 1:
            raise ValueError("checkpoint schema_version must be >= 1")
        if not self.work_unit_id.strip():
            raise ValueError("checkpoint work_unit_id must not be empty")
        if not self.workflow.strip():
            raise ValueError("checkpoint workflow must not be empty")
        if not self.status.strip():
            raise ValueError("checkpoint status must not be empty")
        if not self.stage.strip():
            raise ValueError("checkpoint stage must not be empty")
        if self.sequence < 0:
            raise ValueError("checkpoint sequence must be >= 0")

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "work_unit_id": self.work_unit_id,
            "workflow": self.workflow,
            "status": self.status,
            "stage": self.stage,
            "sequence": self.sequence,
            "next_action": self.next_action,
            "agent_ids": list(self.agent_ids),
            "model_ids": list(self.model_ids),
            "artifact_ids": list(self.artifact_ids),
            "findings": list(self.findings),
            "resumable": self.resumable,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "WorkflowCheckpoint":
        checkpoint = cls(
            schema_version=int(data.get("schema_version", 1)),
            work_unit_id=str(data["work_unit_id"]),
            workflow=str(data["workflow"]),
            status=str(data["status"]),
            stage=str(data["stage"]),
            sequence=int(data.get("sequence", 0)),
            next_action=(
                str(data["next_action"])
                if data.get("next_action") is not None
                else None
            ),
            agent_ids=tuple(str(value) for value in data.get("agent_ids", ())),
            model_ids=tuple(str(value) for value in data.get("model_ids", ())),
            artifact_ids=tuple(str(value) for value in data.get("artifact_ids", ())),
            findings=tuple(str(value) for value in data.get("findings", ())),
            resumable=bool(data.get("resumable", True)),
            metadata=dict(data.get("metadata", {})),
        )
        checkpoint.validate()
        return checkpoint
