"""Project-aware agent activation planning.

Detection is read-only; planning decides which already-defined runtime agents are
relevant to the detected project.  It never installs an IDE integration.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agents.catalog import build_agent_catalog
from core.contracts.classification import ProjectClassification
from core.contracts.profile import DetectionResult
from profiles.classifier import classify_project


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
    classification: ProjectClassification | None = None
    rationale: tuple[str, ...] = ()


_PROFILE_SPECIALISTS = {
    "android-native": {
        "android-architect",
        "android-developer",
        "gradle",
    },
    "ios-native": {
        "ios-architect",
        "ios-developer",
        "xcode",
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


def _evidence_for_profile(
    detections: tuple[DetectionResult, ...], profile_id: str
) -> set[str]:
    evidence: set[str] = set()
    for result in detections:
        if result.profile_id == profile_id:
            evidence.update(result.evidence)
    return evidence


def _technology_specialists(
    profiles: tuple[str, ...],
    detections: tuple[DetectionResult, ...],
) -> set[str]:
    selected: set[str] = set()

    for profile_id in profiles:
        selected.update(_PROFILE_SPECIALISTS.get(profile_id, set()))

        if profile_id == "android-native":
            evidence = _evidence_for_profile(detections, profile_id)
            if "source:kotlin" in evidence or "org.jetbrains.kotlin.android" in evidence:
                selected.add("kotlin-developer")
            if "androidx.compose" in evidence:
                selected.update({"jetpack-compose", "ui-android"})

        elif profile_id == "ios-native":
            evidence = _evidence_for_profile(detections, profile_id)
            if "source:swift" in evidence:
                selected.add("swift-developer")
            if ".xcodeproj" in evidence or ".xcworkspace" in evidence:
                selected.add("xcode")
            if "SwiftUI" in evidence:
                selected.add("swiftui")

    return selected


def build_agent_plan(
    project_root: Path,
    detections: tuple[DetectionResult, ...],
    *,
    approval_threshold: float = 0.70,
) -> AgentPlan:
    profiles = tuple(result.profile_id for result in detections)
    confidence = detections[0].confidence if detections else 0.0
    catalog = build_agent_catalog(profiles)
    specialist_ids = _technology_specialists(profiles, detections)

    available = {agent.id for agent in catalog}
    selected = set(GOVERNANCE_AGENTS) & available
    selected.update(agent_id for agent_id in specialist_ids if agent_id in available)

    excluded = available - selected
    classification = classify_project(detections)
    requires_approval = (
        not detections
        or confidence < approval_threshold
        or classification.requires_approval
    )
    rationale = (
        "governance agents are always available to preserve execution and review boundaries",
        "specialists are selected only from detected technology profiles and direct technology evidence",
    )
    if confidence < approval_threshold:
        rationale += ("detection confidence is below the automatic activation threshold",)
    if classification.ambiguous:
        rationale += classification.reasons

    return AgentPlan(
        project_id=project_root.name.strip() or "project",
        profiles=profiles,
        confidence=confidence,
        selected=tuple(sorted(selected)),
        excluded=tuple(sorted(excluded)),
        requires_approval=requires_approval,
        classification=classification,
        rationale=rationale,
    )
