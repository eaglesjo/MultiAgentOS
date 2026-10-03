#!/bin/bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DELETE_KEYCHAIN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) [[ $# -ge 2 ]] || exit 2; PROJECT_ROOT="$2"; shift 2 ;;
    --delete-keychain) DELETE_KEYCHAIN=1; shift ;;
    -h|--help) echo "Usage: $0 --path <project-root> [--delete-keychain]"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd)" || { echo "ERROR: project root not found: $PROJECT_ROOT" >&2; exit 1; }
PROJECT_ID="$(PROJECT_ROOT="$PROJECT_ROOT" python3 - <<'PY'
import hashlib, os
from pathlib import Path
root=Path(os.environ["PROJECT_ROOT"]).expanduser().resolve()
print(hashlib.sha256(str(root).encode()).hexdigest()[:12])
PY
)"
LABEL="multiagentos.tunnel.project.$PROJECT_ID"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
WRAPPER_PATH="$PROJECT_ROOT/.multiagentos/tunnel-client-launchd.sh"
KEYCHAIN_SERVICE="multiagentos.tunnel.project.$PROJECT_ID.runtime-key"
launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
for _ in {1..50}; do
  if ! launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then break; fi
  sleep 0.1
done
if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  echo "ERROR: tunnel service did not unload: $LABEL" >&2
  exit 1
fi
rm -f "$PLIST_PATH" "$WRAPPER_PATH"
if [[ "$DELETE_KEYCHAIN" -eq 1 ]]; then
  security delete-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" >/dev/null 2>&1 || true
fi
echo "MultiAgentOS project-scoped tunnel-client launchd service removed."
echo "  project:    $PROJECT_ROOT"
echo "  project-id: $PROJECT_ID"
echo "  label:      $LABEL"
