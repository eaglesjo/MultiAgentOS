"""Technology profile contracts for VYRELON."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileSpec:
    id: str
    display_name: str
    detect_files: frozenset[str] = frozenset()
    detect_markers: frozenset[str] = frozenset()
    roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class DetectionResult:
    profile_id: str
    confidence: float
    evidence: tuple[str, ...]
