#!/bin/bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) [[ $# -ge 2 ]] || exit 2; PROJECT_ROOT="$2"; shift 2 ;;
    -h|--help) echo "Usage: $0 --path <project-root>"; exit 0 ;;
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
echo "project: $PROJECT_ROOT"
echo "project-id: $PROJECT_ID"
echo "label: $LABEL"
launchctl print "gui/$(id -u)/$LABEL"
