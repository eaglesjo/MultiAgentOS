#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

usage() {
  cat <<EOF
Usage: $0 --path <project-root>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path)
      [[ $# -ge 2 ]] || { echo "ERROR: --path requires a value." >&2; usage >&2; exit 2; }
      PROJECT_ROOT="$2"
      shift 2
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

echo "Project Root : $PROJECT_ROOT"
echo "Project ID   : $PROJECT_ID"
echo "Service Label: $LABEL"
echo

exec launchctl print "gui/$(id -u)/$LABEL"
