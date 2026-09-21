"""Durable context required to resume a VYRELON workflow."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowResumeContext:
    """Serializable execution context recorded before a resumable boundary."""

    workflow: str
    work_unit_id: str
    review_cycle: int
    max_review_cycles: int
    developer_id: str
    tester_id: str
    reviewer_ids: tuple[str, ...] = ()
    model_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    last_agent_id: str | None = None

    def to_metadata(self) -> dict[str, object]:
        return {
            "workflow": self.workflow,
            "work_unit_id": self.work_unit_id,
            "review_cycle": self.review_cycle,
            "max_review_cycles": self.max_review_cycles,
            "developer_id": self.developer_id,
            "tester_id": self.tester_id,
            "reviewer_ids": list(self.reviewer_ids),
            "model_ids": list(self.model_ids),
            "artifact_ids": list(self.artifact_ids),
            "findings": list(self.findings),
            "last_agent_id": self.last_agent_id,
        }

    @classmethod
    def from_metadata(cls, data: dict[str, object]) -> "WorkflowResumeContext":
        return cls(
            workflow=str(data["workflow"]),
            work_unit_id=str(data["work_unit_id"]),
            review_cycle=int(data["review_cycle"]),
            max_review_cycles=int(data["max_review_cycles"]),
            developer_id=str(data["developer_id"]),
            tester_id=str(data["tester_id"]),
            reviewer_ids=tuple(str(v) for v in data.get("reviewer_ids", ())),
            model_ids=tuple(str(v) for v in data.get("model_ids", ())),
            artifact_ids=tuple(str(v) for v in data.get("artifact_ids", ())),
            findings=tuple(str(v) for v in data.get("findings", ())),
            last_agent_id=(
                str(data["last_agent_id"])
                if data.get("last_agent_id") is not None
                else None
            ),
        )
