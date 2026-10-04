"""Hierarchical project classification contracts.

Classification keeps platform, framework/runtime, and language/toolchain as
independent dimensions. Multiple values are valid for monorepos and ambiguous
projects; confidence is recorded per dimension rather than collapsed into one
flat project label.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationDimension:
    name: str
    values: tuple[str, ...]
    confidence: float
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectClassification:
    platform: ClassificationDimension
    framework_runtime: ClassificationDimension
    language_toolchain: ClassificationDimension
    ambiguous: bool
    reasons: tuple[str, ...] = ()

    @property
    def requires_approval(self) -> bool:
        return (
            self.ambiguous
            or self.platform.confidence < 0.70
            or self.framework_runtime.confidence < 0.70
            or self.language_toolchain.confidence < 0.70
        )
