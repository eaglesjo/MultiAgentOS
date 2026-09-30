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

export MAOS_PROJECT_ROOT="$PROJECT_ROOT"
export MAOS_PYTHON="$PYTHON"
export MAOS_PLIST="$PLIST_PATH"
export MAOS_ALLOW_WRITE="$ALLOW_WRITE"
export MAOS_ALLOW_PROCESS="$ALLOW_PROCESS"

"$PYTHON" - <<'PY'
import os
import plistlib
from pathlib import Path

root = Path(os.environ["MAOS_PROJECT_ROOT"])
python = os.environ["MAOS_PYTHON"]
plist_path = Path(os.environ["MAOS_PLIST"])

args = [
    python, "-m", "multiagentos.cli", "mcp", "serve-http",
    "--path", str(root), "--host", "127.0.0.1", "--port", "8000",
]
if os.environ["MAOS_ALLOW_WRITE"] == "1":
    args.append("--allow-write")
if os.environ["MAOS_ALLOW_PROCESS"] == "1":
    args.append("--allow-process")

plist = {
    "Label": "com.eaglesjo.multiagentos.mcp",
    "ProgramArguments": args,
    "WorkingDirectory": str(root),
    "RunAtLoad": True,
    "KeepAlive": True,
    "ThrottleInterval": 5,
    "ProcessType": "Background",
    "StandardOutPath": str(root / ".multiagentos" / "logs" / "mcp-launchd.log"),
    "StandardErrorPath": str(root / ".multiagentos" / "logs" / "mcp-launchd.error.log"),
    "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
}
plist_path.write_bytes(plistlib.dumps(plist))
print(plist_path)
PY

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
