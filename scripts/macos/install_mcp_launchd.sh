#!/bin/bash
set -euo pipefail

LABEL="com.eaglesjo.multiagentos.mcp"
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$LABEL.plist"
VENV="$PROJECT_ROOT/.venv"
PYTHON="$VENV/bin/python"
HOST="127.0.0.1"
PORT="8000"
ALLOW_WRITE=0
ALLOW_PROCESS=0

usage() {
  cat <<EOF
Usage: $0 [--allow-write] [--allow-process]
Installs MultiAgentOS MCP Streamable HTTP as a macOS per-user launchd service.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow-write) ALLOW_WRITE=1 ;;
    --allow-process) ALLOW_PROCESS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
  echo "ERROR: MultiAgentOS project root not found: $PROJECT_ROOT" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required." >&2
  exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR" "$PROJECT_ROOT/.multiagentos/logs"

if [[ ! -x "$PYTHON" ]]; then
  echo "== Create MultiAgentOS virtual environment =="
  python3 -m venv "$VENV"
fi

echo "== Install/update MultiAgentOS MCP HTTP dependencies =="
"$PYTHON" -m pip install -e "$PROJECT_ROOT[mcp-http]"

echo "== Register MultiAgentOS MCP launchd service =="

ARGS=(
  mcp install
  --path "$PROJECT_ROOT"
  --host "$HOST"
  --port "$PORT"
)
if [[ "$ALLOW_WRITE" == "1" ]]; then
  ARGS+=(--allow-write)
fi
if [[ "$ALLOW_PROCESS" == "1" ]]; then
  ARGS+=(--allow-process)
fi

"$PYTHON" -m multiagentos.cli "${ARGS[@]}"

"$PYTHON" -m multiagentos.cli mcp status --path "$PROJECT_ROOT"

echo "== Stop previous service if present =="
launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true

echo "== Register MultiAgentOS MCP launchd service =="
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"

echo "== Start MultiAgentOS MCP service =="
launchctl kickstart -k "gui/$(id -u)/$LABEL"

launchctl print "gui/$(id -u)/$LABEL" >/dev/null

echo
echo "MultiAgentOS MCP launchd service installed."
echo "  label:    $LABEL"
echo "  project:  $PROJECT_ROOT"
echo "  endpoint: http://$HOST:$PORT/mcp"
echo "  restart:  launchd KeepAlive"
