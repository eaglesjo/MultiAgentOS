"""Handoff artifact contracts."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HandoffArtifact:
    work_unit_id: str
    from_agent: str
    to_agent: str
    summary: str
    artifacts: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewContext:
    """Structured input presented to a reviewer by VYRELON."""

    work_unit_id: str
    artifact_ids: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    last_agent_id: str | None = None
    review_cycle: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewResult:
    approved: bool
    reviewer_id: str
    feedback: str


@dataclass(frozen=True)
class ArtifactContract:
    """Durable artifact passed between VYRELON workflow stages."""

    id: str
    kind: str
    producer_agent_id: str
    content_ref: str
    summary: str = ""
    media_type: str = "text/plain"
    metadata: dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        for name, value in (
            ("id", self.id),
            ("kind", self.kind),
            ("producer_agent_id", self.producer_agent_id),
            ("content_ref", self.content_ref),
        ):
            if not value.strip():
                raise ValueError(f"artifact {name} must not be empty")
