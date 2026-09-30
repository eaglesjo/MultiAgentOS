from __future__ import annotations

import json
import sys


EXPECTED_TOOL = "filesystem.read"


def validate(payload: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if payload.get("status") != "ok":
        errors.append(f"MCP component status is not ok: {payload.get('status')!r}")
    if payload.get("state") != "discovered":
        errors.append(
            f"MCP component state is not discovered: {payload.get('state')!r}"
        )

    details = payload.get("details")
    if not isinstance(details, dict):
        errors.append("MCP discovery details are missing")
        return errors

    if details.get("limited") is True:
        errors.append("MCP discovery evidence is limited")

    tools_list = details.get("tools_list")
    if not isinstance(tools_list, dict):
        errors.append("MCP tools_list evidence is missing")
        return errors

    if tools_list.get("ok") is not True:
        errors.append("MCP tools_list evidence is not ok")
    if tools_list.get("complete") is not True:
        errors.append("MCP tools_list evidence is not complete")
    if tools_list.get("partial") is True:
        errors.append("MCP tools_list evidence is partial")
    if tools_list.get("limited") is True:
        errors.append("MCP tools_list evidence is limited")

    tool_names = tools_list.get("tool_names")
    if not isinstance(tool_names, list) or not all(
        isinstance(name, str) for name in tool_names
    ):
        errors.append("MCP tools_list tool_names is missing or invalid")
    elif EXPECTED_TOOL not in tool_names:
        errors.append(f"expected MCP tool is missing: {EXPECTED_TOOL}")

    return errors


def main() -> int:
    payload = json.load(sys.stdin)
    errors = validate(payload)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "PASS: tunnel-client observed complete MCP discovery "
        f"with expected tool={EXPECTED_TOOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
