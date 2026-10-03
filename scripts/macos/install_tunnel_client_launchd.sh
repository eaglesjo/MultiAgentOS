#!/bin/bash
set -euo pipefail

LABEL_PREFIX="multiagentos.tunnel.project"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PROJECT_ID=""
LABEL=""
PLIST_PATH=""
WRAPPER_PATH=""
KEYCHAIN_SERVICE=""
TUNNEL_ID="${CONTROL_PLANE_TUNNEL_ID:-}"
MCP_SERVER_URL="${MCP_SERVER_URL:-}"
HEALTH_LISTEN_ADDR="${HEALTH_LISTEN_ADDR:-}"
TUNNEL_CLIENT_BIN="${TUNNEL_CLIENT_BIN:-}"

usage() {
  cat <<EOF
Usage: $0 --path <project-root> [--mcp-server-url <url>] [--health-listen-addr <host:port>]

Installs the MultiAgentOS OpenAI tunnel-client as a project-scoped per-user
macOS launchd service. The service identity is derived from the canonical
project path so multiple projects can coexist safely.

Required environment:
  CONTROL_PLANE_TUNNEL_ID
  CONTROL_PLANE_API_KEY

Required configuration (CLI or environment):
  MCP_SERVER_URL       Exact project MCP endpoint, e.g. http://127.0.0.1:8003/mcp
  HEALTH_LISTEN_ADDR   Unique local health address, e.g. 127.0.0.1:18081

Optional environment:
  TUNNEL_CLIENT_BIN    Resolve tunnel-client from PATH when omitted
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path)
      [[ $# -ge 2 ]] || { echo "ERROR: --path requires a value." >&2; usage >&2; exit 2; }
      PROJECT_ROOT="$2"
      shift 2
      ;;
    --mcp-server-url)
      [[ $# -ge 2 ]] || { echo "ERROR: --mcp-server-url requires a value." >&2; usage >&2; exit 2; }
      MCP_SERVER_URL="$2"
      shift 2
      ;;
    --health-listen-addr)
      [[ $# -ge 2 ]] || { echo "ERROR: --health-listen-addr requires a value." >&2; usage >&2; exit 2; }
      HEALTH_LISTEN_ADDR="$2"
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd)" || {
  echo "ERROR: project root not found: $PROJECT_ROOT" >&2
  exit 1
}

if [[ ! -d "$PROJECT_ROOT" ]]; then
  echo "ERROR: project root not found: $PROJECT_ROOT" >&2
  exit 1
fi

if [[ -z "$MCP_SERVER_URL" ]]; then
  echo "ERROR: MCP_SERVER_URL is required." >&2
  echo "Use --mcp-server-url http://127.0.0.1:<project-mcp-port>/mcp" >&2
  exit 1
fi

if [[ -z "$HEALTH_LISTEN_ADDR" ]]; then
  echo "ERROR: HEALTH_LISTEN_ADDR is required." >&2
  echo "Choose a unique local health address for each project." >&2
  exit 1
fi

if [[ -z "$TUNNEL_ID" ]]; then
  echo "ERROR: CONTROL_PLANE_TUNNEL_ID is required." >&2
  exit 1
fi

if [[ -z "${CONTROL_PLANE_API_KEY:-}" ]]; then
  echo "ERROR: CONTROL_PLANE_API_KEY is required for the first installation." >&2
  echo "Export the existing Runtime API key in this shell, then rerun." >&2
  exit 1
fi

if [[ -z "$TUNNEL_CLIENT_BIN" ]]; then
  TUNNEL_CLIENT_BIN="$(command -v tunnel-client || true)"
fi
if [[ -z "$TUNNEL_CLIENT_BIN" || ! -x "$TUNNEL_CLIENT_BIN" ]]; then
  echo "ERROR: tunnel-client binary not found." >&2
  echo "Set TUNNEL_CLIENT_BIN=/absolute/path/to/tunnel-client." >&2
  exit 1
fi
TUNNEL_CLIENT_BIN="$(cd "$(dirname "$TUNNEL_CLIENT_BIN")" && pwd)/$(basename "$TUNNEL_CLIENT_BIN")"

read -r PROJECT_ID LABEL PLIST_PATH WRAPPER_PATH KEYCHAIN_SERVICE <<EOF
$(PROJECT_ROOT="$PROJECT_ROOT" python3 - <<'PY'
import hashlib
import os
from pathlib import Path

root = Path(os.environ["PROJECT_ROOT"]).expanduser().resolve()
project_id = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
label = f"multiagentos.tunnel.project.{project_id}"
plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
wrapper = root / ".multiagentos" / "tunnel-client-launchd.sh"
keychain = f"multiagentos.tunnel.project.{project_id}.runtime-key"
print(project_id, label, plist, wrapper, keychain)
PY
)
EOF

mkdir -p "$LAUNCH_AGENTS_DIR" "$PROJECT_ROOT/.multiagentos/logs"

echo "== Store runtime key in macOS Keychain =="
security add-generic-password \
  -a "$USER" \
  -s "$KEYCHAIN_SERVICE" \
  -w "$CONTROL_PLANE_API_KEY" \
  -U

export MAOS_TUNNEL_LABEL="$LABEL"
export MAOS_PROJECT_ROOT="$PROJECT_ROOT"
export MAOS_WRAPPER="$WRAPPER_PATH"
export MAOS_PLIST="$PLIST_PATH"
export MAOS_KEYCHAIN_SERVICE="$KEYCHAIN_SERVICE"
export MAOS_TUNNEL_ID="$TUNNEL_ID"
export MAOS_MCP_SERVER_URL="$MCP_SERVER_URL"
export MAOS_TUNNEL_CLIENT_BIN="$TUNNEL_CLIENT_BIN"
export MAOS_HEALTH_LISTEN_ADDR="$HEALTH_LISTEN_ADDR"

cat > "$WRAPPER_PATH" <<'EOF'
#!/bin/bash
set -euo pipefail

KEYCHAIN_SERVICE="__KEYCHAIN_SERVICE__"
TUNNEL_ID="__TUNNEL_ID__"
MCP_SERVER_URL="__MCP_SERVER_URL__"
TUNNEL_CLIENT_BIN="__TUNNEL_CLIENT_BIN__"
HEALTH_LISTEN_ADDR="__HEALTH_LISTEN_ADDR__"
LOG_DIR="__LOG_DIR__"

mkdir -p "$LOG_DIR"

CONTROL_PLANE_API_KEY="$(security find-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" -w)"
export CONTROL_PLANE_API_KEY
export CONTROL_PLANE_TUNNEL_ID="$TUNNEL_ID"
export MCP_SERVER_URL="$MCP_SERVER_URL"
export MCP_STARTUP_WAIT_TIMEOUT="60s"
export HEALTH_LISTEN_ADDR="$HEALTH_LISTEN_ADDR"
export LOG_LEVEL="info"
export LOG_FORMAT="struct-text"
export LOG_FILE="$LOG_DIR/tunnel-client.log"

exec "$TUNNEL_CLIENT_BIN" run \
  --control-plane.tunnel-id "$CONTROL_PLANE_TUNNEL_ID" \
  --control-plane.api-key "env:CONTROL_PLANE_API_KEY" \
  --mcp.server-url "$MCP_SERVER_URL"
EOF

python3 - <<'PY'
import os
from pathlib import Path

wrapper = Path(os.environ["MAOS_WRAPPER"])
text = wrapper.read_text()
replacements = {
    "__KEYCHAIN_SERVICE__": os.environ["MAOS_KEYCHAIN_SERVICE"],
    "__TUNNEL_ID__": os.environ["MAOS_TUNNEL_ID"],
    "__MCP_SERVER_URL__": os.environ["MAOS_MCP_SERVER_URL"],
    "__TUNNEL_CLIENT_BIN__": os.environ["MAOS_TUNNEL_CLIENT_BIN"],
    "__HEALTH_LISTEN_ADDR__": os.environ["MAOS_HEALTH_LISTEN_ADDR"],
    "__LOG_DIR__": str(Path(os.environ["MAOS_PROJECT_ROOT"]) / ".multiagentos" / "logs"),
}
for old, new in replacements.items():
    text = text.replace(old, new)
wrapper.write_text(text)
wrapper.chmod(0o700)
PY

python3 - <<'PY'
import os
import plistlib
from pathlib import Path

root = Path(os.environ["MAOS_PROJECT_ROOT"])
plist_path = Path(os.environ["MAOS_PLIST"])
wrapper = Path(os.environ["MAOS_WRAPPER"])

plist = {
    "Label": os.environ["MAOS_TUNNEL_LABEL"],
    "ProgramArguments": [str(wrapper)],
    "WorkingDirectory": str(root),
    "RunAtLoad": True,
    "KeepAlive": True,
    "ThrottleInterval": 10,
    "ProcessType": "Background",
    "StandardOutPath": str(root / ".multiagentos" / "logs" / "tunnel-client-launchd.log"),
    "StandardErrorPath": str(root / ".multiagentos" / "logs" / "tunnel-client-launchd.error.log"),
    "EnvironmentVariables": {
        "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "TUNNEL_CLIENT_NO_UPDATE_CHECK": "1",
    },
}
plist_path.write_bytes(plistlib.dumps(plist))
print(plist_path)
PY

echo "== Stop previous project tunnel service if present =="
launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true

echo "== Wait for previous project tunnel service to unload =="
for _ in {1..50}; do
  if ! launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  echo "ERROR: previous tunnel service did not unload: $LABEL" >&2
  exit 1
fi

echo "== Register project tunnel-client launchd service =="
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"

echo "== Start project tunnel-client launchd service =="
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo
echo "MultiAgentOS project-scoped tunnel-client launchd service installed."
echo "  project:    $PROJECT_ROOT"
echo "  project-id: $PROJECT_ID"
echo "  label:      $LABEL"
echo "  tunnel:     $TUNNEL_ID"
echo "  MCP:        $MCP_SERVER_URL"
echo "  health:     http://$HEALTH_LISTEN_ADDR"
echo "  key:        macOS Keychain ($KEYCHAIN_SERVICE)"
echo
echo "Verify:"
echo "  launchctl print gui/$(id -u)/$LABEL"
echo "  curl -fsS http://$HEALTH_LISTEN_ADDR/readyz"
