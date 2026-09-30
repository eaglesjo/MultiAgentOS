"""Validate tunnel-client managed runtime status JSON without exposing secrets."""

from __future__ import annotations

import json
import sys


def validate(payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if payload.get("process_running") is not True:
        errors.append("process_running must be true")
    if payload.get("healthy") is not True:
        errors.append("healthy must be true")
    if payload.get("ready") is not True:
        errors.append("ready must be true")
    return errors


def main() -> int:
    payload = json.load(sys.stdin)
    errors = validate(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("tunnel-client managed runtime: process_running=true healthy=true ready=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
