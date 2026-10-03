#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DELETE_KEYCHAIN=0

usage() {
  cat <<EOF
Usage: $0 --path <project-root> [--delete-keychain]

Stops and removes only the project-scoped MultiAgentOS tunnel-client
launchd service for the selected project.

Options:
  --path <project-root>  Project owning the tunnel service.
  --delete-keychain      Also remove that project's Runtime API key.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path)
      [[ $# -ge 2 ]] || { echo "ERROR: --path requires a value." >&2; usage >&2; exit 2; }
      PROJECT_ROOT="$2"
      shift 2
      ;;
    --delete-keychain)
      DELETE_KEYCHAIN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd)" || {
  echo "ERROR: project root not found: $PROJECT_ROOT" >&2
  exit 1
}

PROJECT_ID="$(
  PROJECT_ROOT="$PROJECT_ROOT" python3 - <<'PY'
import hashlib
import os
from pathlib import Path

root = Path(os.environ["PROJECT_ROOT"]).expanduser().resolve()
print(hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12])
PY
)"

LABEL="multiagentos.tunnel.project.$PROJECT_ID"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
WRAPPER_PATH="$PROJECT_ROOT/.multiagentos/tunnel-client-launchd.sh"
KEYCHAIN_SERVICE="multiagentos.tunnel.project.$PROJECT_ID.runtime-key"

echo "== Remove project tunnel launchd service =="
launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH" "$WRAPPER_PATH"

if [[ "$DELETE_KEYCHAIN" -eq 1 ]]; then
  security delete-generic-password \
    -a "$USER" \
    -s "$KEYCHAIN_SERVICE" >/dev/null 2>&1 || true
fi

echo
echo "MultiAgentOS project-scoped tunnel-client launchd service removed."
echo "  project:    $PROJECT_ROOT"
echo "  project-id: $PROJECT_ID"
echo "  label:      $LABEL"
if [[ "$DELETE_KEYCHAIN" -eq 1 ]]; then
  echo "  keychain:   removed ($KEYCHAIN_SERVICE)"
else
  echo "  keychain:   preserved ($KEYCHAIN_SERVICE)"
fi
