"""Shared validation for identifiers used in durable state filenames."""

from __future__ import annotations

from pathlib import Path


def state_file_path(root: Path, identifier: str, suffix: str) -> Path:
    """Build a state filename while preventing traversal and symlink escapes."""
    if (
        not isinstance(identifier, str)
        or not identifier.strip()
        or identifier in {".", ".."}
        or any(char in identifier for char in ("/", "\\", ":", "\x00"))
    ):
        raise ValueError("invalid state identifier")

    resolved_root = root.resolve()
    candidate = resolved_root / f"{identifier}{suffix}"
    resolved_candidate = candidate.resolve()
    if (
        resolved_candidate.parent != resolved_root
        or resolved_candidate.name != candidate.name
    ):
        raise ValueError("state path escapes configured root")
    return candidate
