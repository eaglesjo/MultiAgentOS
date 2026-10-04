"""Project profile detection based on independent repository evidence."""

from __future__ import annotations

import json
from pathlib import Path

from core.contracts.profile import DetectionResult, ProfileSpec
from profiles.registry import ProfileRegistry


_IGNORED_DIRS = {
    ".git", "node_modules", "Pods", ".gradle", "build", "dist",
    "venv", ".venv", ".tox", ".mypy_cache", "__pycache__",
}
_SOURCE_SUFFIXES = {".kt", ".java", ".swift", ".m", ".mm", ".tsx", ".ts", ".jsx", ".js"}


class ProfileDetector:
    def __init__(self, registry: ProfileRegistry | None = None) -> None:
        self.registry = registry or ProfileRegistry()

    def detect(self, project_root: Path) -> tuple[DetectionResult, ...]:
        results = []
        for profile in self.registry.list():
            evidence, file_hits, marker_hits = self._evidence(project_root, profile)
            if not evidence:
                continue
            confidence = min(
                1.0,
                (profile.file_weight if file_hits else 0.0)
                + (profile.marker_weight if marker_hits else 0.0),
            )
            results.append(
                DetectionResult(profile.id, confidence, tuple(evidence))
            )
        return tuple(
            sorted(results, key=lambda result: (-result.confidence, result.profile_id))
        )

    def _evidence(
        self, root: Path, profile: ProfileSpec
    ) -> tuple[list[str], bool, bool]:
        evidence: list[str] = []
        file_hits = False
        marker_hits = False

        files = self._files(root)
        names = {path.name for path in files}
        for name in profile.detect_files:
            if name in names:
                evidence.append(name)
                file_hits = True

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
                file_hits = True
                marker_hits = True

        for marker in profile.detect_markers:
            if marker.startswith("."):
                if any(root.glob(f"*{marker}")) or any(
                    path.name.endswith(marker) for path in files
                ):
                    evidence.append(marker)
                    marker_hits = True
            elif self._contains_marker(files, marker):
                evidence.append(marker)
                marker_hits = True

        # Platform structure is independent evidence and avoids treating a
        # single conventional file as proof of a complete native project.
        if profile.id == "android-native":
            if (root / "android").is_dir():
                evidence.append("directory:android")
                file_hits = True
            if any(path.name == "AndroidManifest.xml" for path in files):
                evidence.append("AndroidManifest.xml")
                file_hits = True
            if any(path.name == "gradlew" for path in files):
                evidence.append("gradlew")
                file_hits = True
            if any(path.suffix in {".kt", ".java"} for path in files):
                if any(path.suffix == ".kt" for path in files):
                    evidence.append("source:kotlin")
                    file_hits = True
                if any(path.suffix == ".java" for path in files):
                    evidence.append("source:java")
                    file_hits = True
        elif profile.id == "ios-native":
            if (root / "ios").is_dir():
                evidence.append("directory:ios")
                file_hits = True
            if any(path.name.endswith(".xcodeproj") for path in files):
                evidence.append(".xcodeproj")
                file_hits = True
            if any(path.name.endswith(".xcworkspace") for path in files):
                evidence.append(".xcworkspace")
                file_hits = True
            if any(path.suffix in {".swift", ".m", ".mm"} for path in files):
                if any(path.suffix == ".swift" for path in files):
                    evidence.append("source:swift")
                    file_hits = True
                if any(path.suffix in {".m", ".mm"} for path in files):
                    evidence.append("source:objc")
                    file_hits = True

        return list(dict.fromkeys(evidence)), file_hits, marker_hits

    @staticmethod
    def _files(root: Path) -> list[Path]:
        files: list[Path] = []
        for path in root.rglob("*"):
            if any(part in _IGNORED_DIRS for part in path.parts):
                continue
            if path.is_file():
                files.append(path)
        return files

    @staticmethod
    def _contains_marker(files: list[Path], marker: str) -> bool:
        candidate_suffixes = {".gradle", ".kts", ".swift", ".xml", ".json", ".toml"}
        for path in files:
            if path.name not in {
                "settings.gradle", "settings.gradle.kts", "build.gradle",
                "build.gradle.kts", "Package.swift", "package.json",
            } and path.suffix not in candidate_suffixes:
                continue
            try:
                if marker in path.read_text(encoding="utf-8", errors="ignore")[:20000]:
                    return True
            except OSError:
                continue
        return False
