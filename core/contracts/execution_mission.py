"""Bounded remote execution mission contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MissionOperation(StrEnum):
    TEST = "test"
    PACKAGE = "package"
    VERIFY = "verify"


class MissionDisposition(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ExecutionMission:
    """Immutable request for one bounded remote execution."""

    id: str
    repository: str
    source_sha: str
    workflow: str
    operation: MissionOperation
    ref: str | None = None
    inputs: dict[str, str] = field(default_factory=dict)
    expected_artifacts: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.id.strip():
            raise ValueError("mission id is required")
        if not self.repository.strip():
            raise ValueError("repository is required")
        if len(self.source_sha) != 40:
            raise ValueError("source_sha must be a full 40-character commit SHA")
        int(self.source_sha, 16)
        if not self.workflow.strip():
            raise ValueError("workflow is required")
        if self.ref is not None and not self.ref.strip():
            raise ValueError("ref must be non-empty when provided")


@dataclass(frozen=True)
class ExecutionEvidence:
    """Durable evidence returned by a remote execution."""

    mission_id: str
    run_id: int
    status: str
    conclusion: str | None
    head_sha: str | None
    source_sha: str
    url: str | None = None
    artifacts: tuple[str, ...] = ()
    logs_available: bool = False

    @property
    def disposition(self) -> MissionDisposition:
        if self.conclusion == "success":
            return MissionDisposition.SUCCEEDED
        if self.status in {"queued", "in_progress", "waiting", "requested"}:
            return MissionDisposition.BLOCKED
        return MissionDisposition.FAILED


def verify_execution_evidence(
    mission: ExecutionMission,
    evidence: ExecutionEvidence,
) -> None:
    """Reject evidence that cannot prove the requested mission completed."""

    mission.validate()
    if evidence.mission_id != mission.id:
        raise ValueError("mission identity mismatch")
    if evidence.source_sha != mission.source_sha:
        raise ValueError(
            f"source identity mismatch: expected {mission.source_sha}, "
            f"got {evidence.source_sha}"
        )
    if evidence.status not in {"completed", "success"}:
        raise RuntimeError(f"remote mission is not terminal: {evidence.status}")
    if evidence.conclusion != "success":
        raise RuntimeError(
            f"remote mission failed: conclusion={evidence.conclusion!r}"
        )
    missing = set(mission.expected_artifacts) - set(evidence.artifacts)
    if missing:
        raise RuntimeError(
            "remote mission completed without expected artifacts: "
            + ", ".join(sorted(missing))
        )
