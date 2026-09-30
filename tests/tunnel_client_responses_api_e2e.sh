#!/usr/bin/env bash
set -euo pipefail

# Hosted Secure MCP Tunnel acceptance through the Responses API.
# This is the hosted OpenAI-product boundary: Responses API -> hosted tunnel
# endpoint -> tunnel-client -> MultiAgentOS Streamable HTTP MCP server.
#
# Required:
#   tunnel-client
#   CONTROL_PLANE_TUNNEL_ID
#   CONTROL_PLANE_API_KEY
#   OPENAI_API_KEY
#   OPENAI_MCP_TEST_MODEL
#
# Optional:
#   MULTIAGENTOS_PROJECT_ROOT
#   MULTIAGENTOS_HTTP_PORT
#   MULTIAGENTOS_ALLOW_WRITE (default: 1)
#   OPENAI_BASE_URL (default: https://api.openai.com/v1)

if ! command -v tunnel-client >/dev/null 2>&1; then
  echo "SKIP: tunnel-client is not installed."
  exit 0
fi

for name in CONTROL_PLANE_TUNNEL_ID CONTROL_PLANE_API_KEY OPENAI_API_KEY OPENAI_MCP_TEST_MODEL; do
  if [[ -z "${!name:-}" ]]; then
    echo "SKIP: $name is required."
    echo "Set REQUIRE_TUNNEL_E2E=1 to turn missing prerequisites into a failure."
    if [[ "${REQUIRE_TUNNEL_E2E:-0}" == "1" ]]; then
      exit 2
    fi
    exit 0
  fi
done

ROOT="${MULTIAGENTOS_PROJECT_ROOT:-$PWD}"
PORT="${MULTIAGENTOS_HTTP_PORT:-8000}"
ALLOW_WRITE="${MULTIAGENTOS_ALLOW_WRITE:-1}"
ALIAS="${MULTIAGENTOS_TUNNEL_ALIAS:-multiagentos-responses-e2e-$$}"
BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
WRITE_PATH=".multiagentos/responses-api-tunnel-e2e-$$.txt"
WRITE_CONTENT="responses-api-tunnel-e2e-$$"
SERVER_LOG="${TMPDIR:-/tmp}/multiagentos-responses-mcp-$$.log"

cleanup() {
  tunnel-client runtimes stop "$ALIAS" >/dev/null 2>&1 || true
  kill "${SERVER_PID:-0}" >/dev/null 2>&1 || true
  rm -f "$ROOT/$WRITE_PATH" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "== Start MultiAgentOS Streamable HTTP =="
SERVER_ARGS=(--path "$ROOT" --host 127.0.0.1 --port "$PORT")
if [[ "$ALLOW_WRITE" == "1" ]]; then
  SERVER_ARGS+=(--allow-write)
fi
python3 -m multiagentos.cli mcp serve-http "${SERVER_ARGS[@]}" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

python3 - "$PORT" "$SERVER_PID" "$SERVER_LOG" <<'PY'
import os, socket, sys, time
port, pid, log_path = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
deadline = time.time() + 30
while time.time() < deadline:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise SystemExit(0)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        print(open(log_path, encoding="utf-8").read(), file=sys.stderr)
        raise SystemExit("MultiAgentOS Streamable HTTP server exited")
    time.sleep(0.25)
print(open(log_path, encoding="utf-8").read(), file=sys.stderr)
raise SystemExit("MultiAgentOS Streamable HTTP server did not become reachable")
PY

echo "== Connect managed tunnel-client =="
tunnel-client runtimes connect \
  --alias "$ALIAS" \
  --tunnel-id "$CONTROL_PLANE_TUNNEL_ID" \
  --runtime-api-key env:CONTROL_PLANE_API_KEY \
  --mcp-server-url "http://127.0.0.1:$PORT/mcp"

echo "== Verify managed runtime health =="
tunnel-client runtimes status "$ALIAS" --json \
  | python3 tests/tunnel_client_runtime_status.py

echo "== Invoke MCP through hosted Responses API =="
OPENAI_BASE_URL="$BASE_URL" python3 - "$WRITE_PATH" "$WRITE_CONTENT" "$ALLOW_WRITE" <<'PY'
import json
import os
import sys
import urllib.request

base_url = os.environ["OPENAI_BASE_URL"].rstrip("/")
api_key = os.environ["OPENAI_API_KEY"]
model = os.environ["OPENAI_MCP_TEST_MODEL"]
tunnel_id = os.environ["CONTROL_PLANE_TUNNEL_ID"]
write_path, write_content, allow_write = sys.argv[1:]

if allow_write != "1":
    raise SystemExit("Hosted Responses API gate requires MULTIAGENTOS_ALLOW_WRITE=1")

prompt = (
    "Use the private MCP server tools for this exact acceptance sequence. "
    "First call filesystem.read on README.md. "
    "Then call filesystem.write with path " + write_path + " and content " + write_content + ". "
    "Then call filesystem.read on " + write_path + " to verify the content. "
    "Do not substitute another tool or path. After the tool calls, briefly report the observed final content."
)

payload = {
    "model": model,
    "input": prompt,
    "tools": [{
        "type": "mcp",
        "server_label": "multiagentos",
        "tunnel_id": tunnel_id,
        "allowed_tools": ["filesystem.read", "filesystem.write"],
        "require_approval": "never",
    }],
}

request = urllib.request.Request(
    base_url + "/responses",
    data=json.dumps(payload).encode(),
    method="POST",
    headers={
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    },
)

with urllib.request.urlopen(request, timeout=180) as response:
    result = json.loads(response.read().decode())

output = result.get("output", [])
mcp_calls = [
    item for item in output
    if item.get("type") == "mcp_call" and item.get("server_label") == "multiagentos"
]
names = [item.get("name") for item in mcp_calls]
errors = [item.get("error") for item in mcp_calls if item.get("error")]

if errors:
    raise SystemExit("Hosted MCP call error: " + json.dumps(errors))
if "filesystem.read" not in names:
    raise SystemExit("Hosted Responses API did not invoke filesystem.read")
if "filesystem.write" not in names:
    raise SystemExit("Hosted Responses API did not invoke filesystem.write")

write_calls = [
    item for item in mcp_calls
    if item.get("name") == "filesystem.write"
]
read_calls = [
    item for item in mcp_calls
    if item.get("name") == "filesystem.read"
]
if len(write_calls) < 1 or len(read_calls) < 2:
    raise SystemExit(
        "Expected read -> write -> read MCP call sequence; got " + json.dumps(names)
    )

write_args = json.loads(write_calls[0].get("arguments") or "{}")
if write_args.get("path") != write_path or write_args.get("content") != write_content:
    raise SystemExit("Hosted filesystem.write arguments did not match acceptance target")

last_read = read_calls[-1]
try:
    last_output = json.loads(last_read.get("output") or "{}")
except json.JSONDecodeError:
    last_output = last_read.get("output") or ""
if write_content not in json.dumps(last_output):
    raise SystemExit("Hosted final filesystem.read did not contain the written content")

print("PASS: Responses API invoked the hosted tunnel for filesystem.read -> filesystem.write -> filesystem.read.")
PY
