#!/usr/bin/env bash
set -euo pipefail

# Validate the final local evidence exposed by a managed tunnel-client runtime.
# This does not claim that ChatGPT has invoked a tool; that final hosted-host
# boundary still requires the real connector.

ALIAS="${MULTIAGENTOS_TUNNEL_ALIAS:-agent-execution-runtime-http}"
STATUS_JSON="$(tunnel-client runtimes status "$ALIAS" --json)"

python3 -c '
import json
import sys
p=json.loads(sys.stdin.read())
for key in ("process_running","healthy","ready"):
    if p.get(key) is not True:
        raise SystemExit(f"{key} must be true")
url=p.get("mcp_health_url")
if not url:
    raise SystemExit("mcp_health_url is missing; tunnel-client is too old or MCP health is unavailable")
print(url)
' <<<"$STATUS_JSON" > "${TMPDIR:-/tmp}/multiagentos-mcp-health-$$.url"

MCP_HEALTH_URL="$(cat "${TMPDIR:-/tmp}/multiagentos-mcp-health-$$.url")"
trap 'rm -f "${TMPDIR:-/tmp}/multiagentos-mcp-health-$$.url"' EXIT

echo "== tunnel-client /health/mcp =="
HEALTH_JSON="$(curl --fail --silent --show-error "$MCP_HEALTH_URL")"

python3 tests/tunnel_client_mcp_health.py <<<"$HEALTH_JSON"
