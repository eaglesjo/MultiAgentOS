"""Write structured evidence for one bounded GitHub Actions mission."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_OPERATIONS = {"test", "package", "verify"}
_SOURCE_SHA = re.compile(r"[0-9a-f]{40}")


def build_evidence(
    *,
    mission_id: str,
    source_sha: str,
    operation: str,
    run_id: str | int,
) -> dict[str, Any]:
    """Validate mission identity and return a JSON-safe evidence record."""
    if not mission_id.strip():
        raise ValueError("mission_id must not be empty")
    if not _SOURCE_SHA.fullmatch(source_sha):
        raise ValueError("source_sha must be a full 40-character lowercase commit SHA")
    if operation not in _OPERATIONS:
        raise ValueError(f"unsupported operation: {operation}")
    if not str(run_id).isdigit() or int(run_id) <= 0:
        raise ValueError("run_id must be a positive integer")

    return {
        "mission_id": mission_id,
        "source_sha": source_sha,
        "operation": operation,
        "run_id": int(run_id),
        "status": "completed",
        "conclusion": "success",
    }


def write_evidence(
    output_path: Path,
    *,
    mission_id: str,
    source_sha: str,
    operation: str,
    run_id: str | int,
) -> dict[str, Any]:
    """Atomically write validated mission evidence as UTF-8 JSON."""
    evidence = build_evidence(
        mission_id=mission_id,
        source_sha=source_sha,
        operation=operation,
        run_id=run_id,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    return evidence


def main() -> None:
    write_evidence(
        Path("mission-evidence/result.json"),
        mission_id=os.environ["MISSION_ID"],
        source_sha=os.environ["SOURCE_SHA"],
        operation=os.environ["OPERATION"],
        run_id=os.environ["GITHUB_RUN_ID"],
    )


if __name__ == "__main__":
    main()
