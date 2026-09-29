"""Workspace/path security for AGENT_EXECUTION_RUNTIME local tools."""

from __future__ import annotations

from pathlib import Path


class PathSecurityError(PermissionError):
    """Raised when a path escapes the configured local workspace."""


class PathPolicy:
    """Resolve paths and optionally confine them to explicit workspace roots."""

    def __init__(self, roots: tuple[str, ...] = ()) -> None:
        self.roots = tuple(Path(root).expanduser().resolve() for root in roots)

    def resolve(self, path: str | Path, *, must_exist: bool = False) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute() and self.roots:
            candidate = self.roots[0] / candidate
        resolved = candidate.resolve(strict=must_exist)
        self._check_allowed(resolved)
        return resolved

    def _check_allowed(self, path: Path) -> None:
        if not self.roots:
            return
        if not any(path == root or root in path.parents for root in self.roots):
            allowed = ", ".join(str(root) for root in self.roots)
            raise PathSecurityError(f"path is outside allowed roots: {path}; allowed={allowed}")
