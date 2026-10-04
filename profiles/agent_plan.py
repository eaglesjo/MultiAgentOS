"""Project-aware agent activation planning.

Detection is read-only; planning decides which already-defined runtime agents are
relevant to the detected project.  It never installs an IDE integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.catalog import build_agent_catalog
from core.contracts.profile import DetectionResult


GOVERNANCE_AGENTS = (
    "file-picker",
    "planner",
    "editor",
    "executor",
    "terminal-monitor",
    "reviewer",
    "debugger",
)


@dataclass(frozen=True)
class AgentPlan:
    project_id: str
    profiles: tuple[str, ...]
    confidence: float
    selected: tuple[str, ...]
    excluded: tuple[str, ...]
    requires_approval: bool
    rationale: tuple[str, ...] = ()


_PROFILE_SPECIALISTS = {
    "android-native": {
        "android-architect",
        "android-developer",
        "kotlin-developer",
        "jetpack-compose",
        "gradle",
        "ui-android",
    },
    "ios-native": {
        "ios-architect",
        "ios-developer",
        "swift-developer",
        "swiftui",
        "xcode",
        "ui-ios",
    },
    "react-native": {
        "architect",
        "developer",
        "react-native-developer",
        "ui",
        "ui-react-native",
        "navigation",
        "state-management",
    },
}


def build_agent_plan(
    project_root: Path,
    detections: tuple[DetectionResult, ...],
    *,
    approval_threshold: float = 0.70,
) -> AgentPlan:
    profiles = tuple(result.profile_id for result in detections)
    confidence = detections[0].confidence if detections else 0.0
    catalog = build_agent_catalog(profiles)
    specialist_ids = set().union(*(_PROFILE_SPECIALISTS.get(p, set()) for p in profiles))

    available = {agent.id for agent in catalog}
    selected = set(GOVERNANCE_AGENTS) & available
    selected.update(agent_id for agent_id in specialist_ids if agent_id in available)

    excluded = available - selected
    requires_approval = not detections or confidence < approval_threshold
    rationale = (
        "governance agents are always available to preserve execution and review boundaries",
        "specialists are selected only from detected technology profiles",
    )
    if requires_approval:
        rationale += ("detection confidence is below the automatic activation threshold",)

    return AgentPlan(
        project_id=project_root.name.strip() or "project",
        profiles=profiles,
        confidence=confidence,
        selected=tuple(sorted(selected)),
        excluded=tuple(sorted(excluded)),
        requires_approval=requires_approval,
        rationale=rationale,
    )
