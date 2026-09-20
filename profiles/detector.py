"""Project profile detection based on repository evidence."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.profile import DetectionResult, ProfileSpec
from profiles.registry import ProfileRegistry


_IGNORED_DIRS = {".git", "node_modules", "Pods", ".gradle", "build", "dist", "venv", ".venv"}


class ProfileDetector:
    def __init__(self, registry: ProfileRegistry | None = None) -> None:
        self.registry = registry or ProfileRegistry()

    def detect(self, project_root: Path) -> tuple[DetectionResult, ...]:
        results = []
        for profile in self.registry.list():
            evidence = self._evidence(project_root, profile)
            if evidence:
                confidence = min(
                    1.0,
                    len(evidence) / max(1, len(profile.detect_files) + len(profile.detect_markers)),
                )
                results.append(DetectionResult(profile.id, confidence, tuple(evidence)))
        return tuple(sorted(results, key=lambda result: (-result.confidence, result.profile_id)))

    def _evidence(self, root: Path, profile: ProfileSpec) -> list[str]:
        evidence = [name for name in profile.detect_files if (root / name).exists()]

        package = root / "package.json"
        if package.exists() and "react-native" in profile.detect_markers:
            try:
                data = json.loads(package.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            dependencies = {
                **data.get("dependencies", {}),
                **data.get("devDependencies", {}),
            }
            if "react-native" in dependencies:
                evidence.append("package.json:react-native")

        for marker in profile.detect_markers:
            if marker.startswith("."):
                if any(root.glob(f"*{marker}")):
                    evidence.append(marker)
            elif self._contains_marker(root, marker):
                evidence.append(marker)

        return list(dict.fromkeys(evidence))

    def _contains_marker(self, root: Path, marker: str) -> bool:
        candidate_names = {"settings.gradle", "settings.gradle.kts", "build.gradle", "build.gradle.kts", "Package.swift"}
        for path in root.rglob("*"):
            if any(part in _IGNORED_DIRS for part in path.parts):
                continue
            if path.is_file() and (path.name in candidate_names or path.suffix in {".gradle", ".kts", ".swift"}):
                try:
                    if marker in path.read_text(encoding="utf-8", errors="ignore")[:20000]:
                        return True
                except OSError:
                    continue
        return False
