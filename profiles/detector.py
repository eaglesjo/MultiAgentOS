"""Project profile detection based on repository evidence."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.profile import DetectionResult, ProfileSpec
from profiles.registry import ProfileRegistry


class ProfileDetector:
    def __init__(self, registry: ProfileRegistry | None = None) -> None:
        self.registry = registry or ProfileRegistry()

    def detect(self, project_root: Path) -> tuple[DetectionResult, ...]:
        results = []
        for profile in self.registry.list():
            evidence = self._evidence(project_root, profile)
            if evidence:
                confidence = min(1.0, len(evidence) / max(1, len(profile.detect_files) + len(profile.detect_markers)))
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
            else:
                for candidate in root.rglob("*"):
                    if candidate.is_file() and marker in candidate.read_text(
                        encoding="utf-8", errors="ignore"
                    )[:20000]:
                        evidence.append(marker)
                        break
        return list(dict.fromkeys(evidence))
