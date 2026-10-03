"""WorkUnit scope-lock contracts inspired by PetTarotReading governance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScopeLock:
    """Explicit file boundary for one WorkUnit or plan step.

    Empty allowed_files means the scope is not file-specific. Excluded files
    always remain forbidden when present.
    """

    allowed_files: tuple[str, ...] = ()
    excluded_files: tuple[str, ...] = ()

    def validate(self) -> None:
        overlap = set(self.allowed_files) & set(self.excluded_files)
        if overlap:
            raise ValueError(
                f"ScopeLock contains files in both allowed and excluded scope: "
                f"{sorted(overlap)}"
            )

    def allows(self, path: str) -> bool:
        self.validate()
        if path in self.excluded_files:
            return False
        if not self.allowed_files:
            return True
        return path in self.allowed_files

    def contains(self, child: "ScopeLock") -> bool:
        """Return whether a child scope stays within this scope boundary."""
        self.validate()
        child.validate()
        if self.allowed_files:
            if not child.allowed_files:
                return False
            if not set(child.allowed_files).issubset(self.allowed_files):
                return False
        if set(child.allowed_files) & set(self.excluded_files):
            return False
        return True
