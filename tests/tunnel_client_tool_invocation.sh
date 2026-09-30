#!/usr/bin/env bash
set -euo pipefail

if ! command -v tunnel-client >/dev/null 2>&1; then
  echo "SKIP: tunnel-client is not installed."
  exit 0
fi

ROOT="$MULTIAGENTOS_PROJECT_ROOT"
if [[ -z "$ROOT" ]]; then ROOT="$PWD"; fi
PORT="$MULTIAGENTOS_HTTP_PORT"
if [[ -z "$PORT" ]]; then PORT=8000; fi
ALLOW_WRITE="$MULTIAGENTOS_ALLOW_WRITE"
if [[ -z "$ALLOW_WRITE" ]]; then ALLOW_WRITE=1; fi
TMP="$TMPDIR"
if [[ -z "$TMP" ]]; then TMP=/tmp; fi
RUN_ID="$$"
SERVER_LOG="$TMP/multiagentos-tunnel-server-$RUN_ID.log"
PROXY_LOG="$TMP/multiagentos-tunnel-proxy-$RUN_ID.log"
WRITE_PATH=".multiagentos/tunnel-client-tool-e2e-$RUN_ID.txt"
WRITE_CONTENT="tunnel-client-tool-e2e-$RUN_ID"

cleanup() {
  kill "$PROXY_PID" >/dev/null 2>&1 || true
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  rm -f "$ROOT/$WRITE_PATH" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

SERVER_ARGS=(--path "$ROOT" --host 127.0.0.1 --port "$PORT")
if [[ "$ALLOW_WRITE" == "1" ]]; then SERVER_ARGS+=(--allow-write); fi

echo "== Start MultiAgentOS Streamable HTTP =="
python3 -m multiagentos.cli mcp serve-http "${SERVER_ARGS[@]}" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

python3 - "$PORT" <<'PY'
import socket, sys, time
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

echo "== Start tunnel-client local forwarding proxy =="
tunnel-client dev proxy \
  --tunnel-id "tunnel_00000000000000000000000000000001" \
  --mcp-server-url "http://127.0.0.1:$PORT/mcp" \
  --listen 127.0.0.1:0 \
  --print-json >"$PROXY_LOG" 2>&1 &
PROXY_PID=$!

MCP_URL="$(
python3 - "$PROXY_LOG" <<'PY'
import json, sys, time
path = sys.argv[1]
deadline = time.time() + 30
while time.time() < deadline:
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                url = payload.get("mcp_url")
                if isinstance(url, str) and url:
                    print(url)
                    raise SystemExit(0)
    except FileNotFoundError:
        pass
    time.sleep(0.25)
raise SystemExit("tunnel-client dev proxy did not publish an MCP URL")
PY
)"

echo "MCP ingress: $MCP_URL"

python3 - "$MCP_URL" "$WRITE_PATH" "$WRITE_CONTENT" "$ALLOW_WRITE" <<'PY'
import json, sys, urllib.request

url, write_path, write_content, allow_write = sys.argv[1:]
counter = 0

def post(method, params=None, session_id=None):
    global counter
    counter += 1
    body = {"jsonrpc": "2.0", "id": counter, "method": method}
    if params is not None:
        body["params"] = params
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.status, dict(response.headers), response.read().decode()

def notify(method, params, session_id):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Mcp-Session-Id": session_id,
    }
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=30):
        pass

status, headers, raw = post("initialize", {
    "protocolVersion": "2025-03-26",
    "capabilities": {},
    "clientInfo": {"name": "MultiAgentOS tunnel-client e2e", "version": "1.0"},
})
if status != 200:
    raise SystemExit("initialize failed: HTTP " + str(status))
payload = json.loads(raw)
if "error" in payload:
    raise SystemExit("initialize error: " + json.dumps(payload["error"]))
session_id = headers.get("Mcp-Session-Id")
if not session_id:
    raise SystemExit("initialize did not return Mcp-Session-Id")
notify("notifications/initialized", {}, session_id)

_, _, raw = post("tools/list", {}, session_id)
payload = json.loads(raw)
if "error" in payload:
    raise SystemExit("tools/list error: " + json.dumps(payload["error"]))
tool_names = {item.get("name") for item in payload.get("result", {}).get("tools", [])}
if "filesystem.read" not in tool_names:
    raise SystemExit("filesystem.read was not forwarded through tunnel-client")

def call(name, arguments):
    _, _, raw = post("tools/call", {"name": name, "arguments": arguments}, session_id)
    payload = json.loads(raw)
    if "error" in payload:
        raise SystemExit(name + " error: " + json.dumps(payload["error"]))
    result = payload.get("result", {})
    if result.get("isError") is True:
        raise SystemExit(name + " returned isError=true: " + json.dumps(result))
    return result

if not call("filesystem.read", {"path": "README.md"}).get("content"):
    raise SystemExit("filesystem.read returned no content")

if allow_write == "1":
    if "filesystem.write" not in tool_names:
        raise SystemExit("filesystem.write was not forwarded through tunnel-client")
    call("filesystem.write", {"path": write_path, "content": write_content})
    verify = call("filesystem.read", {"path": write_path})
    if write_content not in json.dumps(verify):
        raise SystemExit("filesystem.write/read round-trip mismatch")

print("PASS: tunnel-client forwarded tools/list, filesystem.read"
      + (", filesystem.write, and the write/read round trip." if allow_write == "1" else "."))
PY
