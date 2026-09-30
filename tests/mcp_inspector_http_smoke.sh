#!/usr/bin/env bash
set -euo pipefail

SERVER_URL="${MCP_SERVER_URL:-http://127.0.0.1:8000/mcp}"
INSPECTOR_VERSION="${MCP_INSPECTOR_VERSION:-2.5.0}"

exec npx --yes "@modelcontextprotocol/inspector@${INSPECTOR_VERSION}" --cli \
  --transport http \
  --server-url "${SERVER_URL}" \
  --method tools/list
