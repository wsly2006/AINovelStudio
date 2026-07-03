#!/usr/bin/env bash
# 一键启动：后端 + 前端跑在同一个终端里，Ctrl+C 一并退出。
# 用法：./scripts/run.sh [backend_port] [frontend_port]
#   默认 backend=8765, frontend=5173
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${1:-8765}"
FRONTEND_PORT="${2:-5173}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1"; exit 1; }; }
need uv
need npm

if [ ! -d "backend/.venv" ]; then
  echo "[setup] uv sync ..."
  (cd backend && uv sync)
fi
if [ ! -d "frontend/node_modules" ]; then
  echo "[setup] npm install ..."
  (cd frontend && npm install)
fi

export BACKEND_PORT FRONTEND_PORT

echo "[start] backend  -> http://127.0.0.1:${BACKEND_PORT}"
echo "[start] frontend -> http://localhost:${FRONTEND_PORT}"

( cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" ) &
BACKEND_PID=$!

( cd frontend && npm run dev ) &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "[stop] killing backend ($BACKEND_PID) and frontend ($FRONTEND_PID)"
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup INT TERM

wait
