#!/usr/bin/env bash
set -euo pipefail

# Final, environment-specific Secure MCP Tunnel acceptance test.
# This intentionally requires real tunnel credentials and a provisioned tunnel.
#
# Required:
#   tunnel-client
#   CONTROL_PLANE_TUNNEL_ID
#   CONTROL_PLANE_API_KEY
#
# Optional:
#   MULTIAGENTOS_TUNNEL_ALIAS
#   MULTIAGENTOS_PROJECT_ROOT
#   MULTIAGENTOS_HTTP_PORT

if ! command -v tunnel-client >/dev/null 2>&1; then
  echo "SKIP: tunnel-client is not installed."
  exit 0
fi

if [[ -z "${CONTROL_PLANE_TUNNEL_ID:-}" || -z "${CONTROL_PLANE_API_KEY:-}" ]]; then
  echo "SKIP: CONTROL_PLANE_TUNNEL_ID and CONTROL_PLANE_API_KEY are required."
  echo "Set REQUIRE_TUNNEL_E2E=1 to turn missing prerequisites into a failure."
  if [[ "${REQUIRE_TUNNEL_E2E:-0}" == "1" ]]; then
    exit 2
  fi
  exit 0
fi

ROOT="${MULTIAGENTOS_PROJECT_ROOT:-$PWD}"
PORT="${MULTIAGENTOS_HTTP_PORT:-8000}"
ALIAS="${MULTIAGENTOS_TUNNEL_ALIAS:-multiagentos-e2e-$$}"
SERVER_URL="http://127.0.0.1:${PORT}/mcp"
SERVER_LOG="${TMPDIR:-/tmp}/multiagentos-mcp-$$.log"

cleanup() {
  tunnel-client runtimes stop "$ALIAS" >/dev/null 2>&1 || true
  kill "${SERVER_PID:-0}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "== Start MultiAgentOS Streamable HTTP =="
python3 -m multiagentos.cli mcp serve-http \
  --path "$ROOT" \
  --host 127.0.0.1 \
  --port "$PORT" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$

python3 - "$PORT" <<'PY'
import socket
import sys
import time

port = int(sys.argv[1])
deadline = time.time() + 30
while time.time() < deadline:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(0)
    time.sleep(0.25)
raise SystemExit("MultiAgentOS Streamable HTTP server did not become reachable")
PY

echo "== Connect tunnel-client =="
tunnel-client runtimes connect \
  --alias "$ALIAS" \
  --tunnel-id "$CONTROL_PLANE_TUNNEL_ID" \
  --runtime-api-key env:CONTROL_PLANE_API_KEY \
  --mcp-server-url "$SERVER_URL"

echo "== Verify managed runtime =="
tunnel-client runtimes status "$ALIAS" --json \
  | python3 tests/tunnel_client_runtime_status.py

echo "PASS: tunnel-client managed runtime is running, healthy, and ready."
