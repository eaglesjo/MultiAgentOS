#!/usr/bin/env python3
"""Minimal Responses API -> Secure MCP Tunnel smoke test for MultiAgentOS.

This script intentionally uses a dedicated API-key environment variable and asks
the model to perform real filesystem.write/read calls through the configured
Secure MCP Tunnel. It does not expose the API key in output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5"
DEFAULT_KEY_ENV = "MULTIAGENTOS_OPENAI_API_KEY"
DEFAULT_TEST_FILE = "MCP_TUNNEL_TEST.md"
TEST_CONTENT = "MultiAgentOS Responses API MCP tunnel smoke test.\\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tunnel-id", default=os.getenv("MULTIAGENTOS_TUNNEL_ID"))
    parser.add_argument("--model", default=os.getenv("MULTIAGENTOS_OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key-env", default=DEFAULT_KEY_ENV)
    parser.add_argument("--test-file", default=DEFAULT_TEST_FILE)
    return parser.parse_args()


def request(api_key: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Responses API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Responses API request failed: {exc.reason}") from exc


def collect_mcp_calls(response: dict) -> list[dict]:
    calls: list[dict] = []
    for item in response.get("output", []):
        if item.get("type") == "mcp_call":
            calls.append(item)
    return calls


def main() -> int:
    args = parse_args()
    api_key = os.getenv(args.api_key_env)
    if not api_key:
        print(f"ERROR: {args.api_key_env} is not set.", file=sys.stderr)
        return 2
    if not args.tunnel_id:
        print("ERROR: set MULTIAGENTOS_TUNNEL_ID or pass --tunnel-id.", file=sys.stderr)
        return 2

    target = Path(args.test_file).as_posix()
    prompt = (
        "Use the private MultiAgentOS MCP server through the Secure MCP Tunnel. "
        f"First call filesystem.write on {target} with exactly this text: "
        f"{TEST_CONTENT!r}. Then call filesystem.read on {target}. "
        "Actually perform both tool calls; do not merely describe what you would do. "
        "In your final response, report the read-back text."
    )
    payload = {
        "model": args.model,
        "input": prompt,
        "tools": [
            {
                "type": "mcp",
                "server_label": "multiagentos",
                "tunnel_id": args.tunnel_id,
                "allowed_tools": ["filesystem.read", "filesystem.write"],
                "require_approval": "never",
            }
        ],
    }

    response = request(api_key, payload)
    calls = collect_mcp_calls(response)
    call_names = [item.get("name") for item in calls]
    output_text = response.get("output_text", "")

    print(f"model={args.model}")
    print(f"tunnel_id={args.tunnel_id}")
    print(f"mcp_calls={call_names}")
    print(f"output={output_text}")

    if "filesystem.write" not in call_names:
        print("ERROR: filesystem.write was not observed.", file=sys.stderr)
        return 1
    if "filesystem.read" not in call_names:
        print("ERROR: filesystem.read was not observed.", file=sys.stderr)
        return 1
    if TEST_CONTENT.strip() not in output_text:
        print("ERROR: expected read-back content was not present.", file=sys.stderr)
        return 1

    print(f"PASS: real MCP write/read completed for {target}.")
    print(f"Cleanup: rm -f {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
