"""Workspace-aware project discovery and analysis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from core.contracts.classification import ProjectClassification
from core.contracts.profile import DetectionResult
from profiles.classifier import classify_project
from profiles.detector import ProfileDetector


@dataclass(frozen=True)
class WorkspaceSpec:
    id: str
    path: Path
    kind: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkspaceAnalysis:
    spec: WorkspaceSpec
    detections: tuple[DetectionResult, ...]
    classification: ProjectClassification


_IGNORED_DIRS = {
    ".git", "node_modules", "Pods", ".gradle", "build", "dist",
    "venv", ".venv", ".tox", ".mypy_cache", "__pycache__",
}


def discover_workspaces(project_root: Path) -> tuple[WorkspaceSpec, ...]:
    root = project_root.resolve()
    members: dict[Path, WorkspaceSpec] = {}

    def add(path: Path, kind: str, evidence: str) -> None:
        resolved = path.resolve()
        if resolved == root or not resolved.is_dir() or root not in resolved.parents:
            return
        if any(part in _IGNORED_DIRS for part in resolved.relative_to(root).parts):
            return
        current = members.get(resolved)
        if current is None:
            members[resolved] = WorkspaceSpec(
                resolved.relative_to(root).as_posix(), resolved, kind, (evidence,)
            )
        elif evidence not in current.evidence:
            members[resolved] = WorkspaceSpec(
                current.id, current.path, current.kind, current.evidence + (evidence,)
            )

    package = root / "package.json"
    if package.is_file():
        try:
            data = json.loads(package.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        patterns = data.get("workspaces", [])
        if isinstance(patterns, dict):
            patterns = patterns.get("packages", [])
        if isinstance(patterns, list):
            for pattern in patterns:
                if not isinstance(pattern, str):
                    continue
                for path in root.glob(pattern):
                    if path.is_dir() and (path / "package.json").is_file():
                        add(path, "npm-workspace", f"package.json:workspaces:{pattern}")

    pnpm = root / "pnpm-workspace.yaml"
    if pnpm.is_file():
        in_packages = False
        try:
            lines = pnpm.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("packages:"):
                in_packages = True
                continue
            if in_packages and stripped.startswith("-"):
                pattern = stripped[1:].strip().strip("'").strip('"')
                for path in root.glob(pattern):
                    if path.is_dir() and (path / "package.json").is_file():
                        add(path, "pnpm-workspace", f"pnpm-workspace.yaml:{pattern}")
            elif in_packages and stripped and not line.startswith((" ", "\t")):
                in_packages = False

    for settings_name in ("settings.gradle", "settings.gradle.kts"):
        settings = root / settings_name
        if not settings.is_file():
            continue
        try:
            content = settings.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in re.finditer(r"""include\s*\(([^)]*)\)|include\s+([^\n]+)""", content):
            raw = match.group(1) or match.group(2) or ""
            for project in re.findall(r"""['"](:[^'"]+)['"]""", raw):
                relative = Path(*[part for part in project.split(":") if part])
                add(root / relative, "gradle-subproject", f"{settings_name}:{project}")
        for match in re.finditer(
            r"""project\(['"](:[^'"]+)['"]\)\.projectDir\s*=\s*file\(['"]([^'"]+)['"]\)""",
            content,
        ):
            add(root / match.group(2), "gradle-subproject", f"{settings_name}:{match.group(1)}:projectDir")
        for match in re.finditer(r"""includeBuild\s*\(?\s*['"]([^'"]+)['"]""", content):
            add(root / match.group(1), "gradle-included-build", f"{settings_name}:includeBuild")

    for manifest in root.rglob("Package.swift"):
        if any(part in _IGNORED_DIRS for part in manifest.relative_to(root).parts):
            continue
        if manifest.parent != root:
            add(manifest.parent, "swift-package", "Package.swift")

    return (
        WorkspaceSpec("root", root, "repository-root", ("repository root",)),
        *sorted(members.values(), key=lambda item: item.id),
    )


def analyze_workspaces(project_root: Path, detector: ProfileDetector | None = None) -> tuple[WorkspaceAnalysis, ...]:
    root = project_root.resolve()
    detector = detector or ProfileDetector()
    specs = discover_workspaces(root)
    recursive_root = len(specs) == 1
    return tuple(
        WorkspaceAnalysis(
            spec,
            (detections := detector.detect(
                spec.path, recursive=(recursive_root or spec.id != "root")
            )),
            classify_project(detections),
        )
        for spec in specs
    )


def aggregate_detections(analyses: tuple[WorkspaceAnalysis, ...]) -> tuple[DetectionResult, ...]:
    by_profile: dict[str, tuple[float, list[str]]] = {}
    for analysis in analyses:
        for result in analysis.detections:
            confidence, evidence = by_profile.get(result.profile_id, (0.0, []))
            by_profile[result.profile_id] = (
                max(confidence, result.confidence),
                evidence + [item for item in result.evidence if item not in evidence],
            )
    return tuple(
        sorted(
            (DetectionResult(profile_id, confidence, tuple(evidence))
             for profile_id, (confidence, evidence) in by_profile.items()),
            key=lambda result: (-result.confidence, result.profile_id),
        )
    )
