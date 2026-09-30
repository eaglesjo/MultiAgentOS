"""Validate tunnel-client managed runtime status JSON without exposing secrets."""

from __future__ import annotations

import json
import sys
from typing import Any


def _component_ok(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.lower() in {"ok", "healthy", "ready", "true"}
    if isinstance(value, dict):
        status = value.get("status")
        state = value.get("state")
        return status == "ok" or state in {"healthy", "ready", "running"}
    return False


def validate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("process_running", "healthy", "ready"):
        if payload.get(field) is not True:
            errors.append(f"{field} must be true")

    poll = payload.get("control_plane_poll_health")
    if poll is None:
        errors.append("control_plane_poll_health is missing")
    elif not _component_ok(poll):
        errors.append("control_plane_poll_health is not healthy")

    return errors


def main() -> int:
    payload = json.load(sys.stdin)
    errors = validate(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "tunnel-client managed runtime: "
        "process_running=true healthy=true ready=true control_plane_poll_health=ok"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
