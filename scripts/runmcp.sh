#!/usr/bin/env bash
# Start the MCP server over a network transport so external clients can connect.
# Usage: ./scripts/runmcp.sh [port] [transport] [host]
#   defaults: port=11889  transport=streamable-http  host=127.0.0.1
# Client URLs:
#   streamable-http -> http://host:port/mcp
#   sse             -> http://host:port/sse
# Pass host=0.0.0.0 to accept LAN clients (add your own auth before exposing).
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MCP_PORT="${1:-11889}"
MCP_TRANSPORT="${2:-streamable-http}"
MCP_HOST="${3:-127.0.0.1}"

# Enable write-capable MCP tools (update_*, generate_chapter_content, ...).
# Comment out to run the server in read-only mode.
export AI_NOVEL_MCP_ENABLE_WRITES=true

command -v uv >/dev/null 2>&1 || { echo "Missing command: uv"; exit 1; }

if [ ! -d "backend/.venv" ]; then
  echo "[setup] uv sync ..."
  (cd backend && uv sync)
fi

echo "[start] mcp ${MCP_TRANSPORT} -> http://${MCP_HOST}:${MCP_PORT}"
echo "[hint]  press Ctrl+C to stop"

cd backend
exec uv run python -m app.mcp.server \
  --transport "$MCP_TRANSPORT" \
  --host "$MCP_HOST" \
  --port "$MCP_PORT"
