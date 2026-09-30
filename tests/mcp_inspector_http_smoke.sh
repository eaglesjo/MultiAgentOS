#!/usr/bin/env bash
set -euo pipefail

SERVER_URL="${MCP_SERVER_URL:-http://127.0.0.1:8000/mcp}"
INSPECTOR_VERSION="${MCP_INSPECTOR_VERSION:-2.5.0}"

echo "== MCP Inspector: tools/list =="
npx --yes "@modelcontextprotocol/inspector@${INSPECTOR_VERSION}" \
  --cli "${SERVER_URL}" \
  --transport http \
  --method tools/list

echo "== MCP Inspector: filesystem.read =="
npx --yes "@modelcontextprotocol/inspector@${INSPECTOR_VERSION}" \
  --cli "${SERVER_URL}" \
  --transport http \
  --method tools/call \
  --tool-name filesystem.read \
  --tool-arg 'path=.github/workflows/agent-execution-runtime-foundation.yml'

# The command above must exit zero; Inspector reports MCP tool errors via its process status.
