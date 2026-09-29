"""Resolve technology detections into stable AGENT_EXECUTION_RUNTIME project and agent profiles."""

from __future__ import annotations

from pathlib import Path

from agents.catalog import build_agent_catalog
from core.contracts.profile import AgentProfile, DetectionResult, ProjectProfile
from profiles.detector import ProfileDetector


class ProfileResolver:
    """Build a deterministic ProjectProfile and AgentProfile set for a project."""

    def __init__(self, detector: ProfileDetector | None = None) -> None:
        self.detector = detector or ProfileDetector()

    def resolve(self, project_root: Path) -> tuple[ProjectProfile, tuple[AgentProfile, ...]]:
        detections = self.detector.detect(project_root)
        return self.resolve_detections(project_root, detections)

    def resolve_detections(
        self,
        project_root: Path,
        detections: tuple[DetectionResult, ...],
    ) -> tuple[ProjectProfile, tuple[AgentProfile, ...]]:
        profile_ids = tuple(result.profile_id for result in detections)
        contracts = build_agent_catalog(profile_ids)
        agents = tuple(
            AgentProfile(
                id=agent.id,
                role=agent.role,
                profile_ids=profile_ids,
                capabilities=agent.capabilities,
                tools=agent.tools,
                permissions=agent.permissions,
                model_ids=agent.model_ids,
                metadata=dict(agent.metadata),
            )
            for agent in contracts
        )
        project = ProjectProfile(
            id=self._project_id(project_root),
            root=str(project_root),
            technology_profile_ids=profile_ids,
            agent_profile_ids=tuple(agent.id for agent in agents),
            metadata={
                "detection": [
                    {
                        "profile": result.profile_id,
                        "confidence": result.confidence,
                        "evidence": list(result.evidence),
                    }
                    for result in detections
                ]
            },
        )
        return project, agents

    @staticmethod
    def _project_id(project_root: Path) -> str:
        name = project_root.name.strip()
        return name or "project"
