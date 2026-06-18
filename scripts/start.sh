#!/usr/bin/env bash
# 一键启动:后端 + 前端,用 Ctrl+C 一并退出。
# 适用于 Git Bash / WSL / macOS / Linux。
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# --- 检查工具 ---
need() { command -v "$1" >/dev/null 2>&1 || { echo "缺少命令: $1"; exit 1; }; }
need uv
need npm

# --- 安装依赖(首次或锁文件变了时自动跑) ---
if [ ! -d "backend/.venv" ]; then
  echo "[setup] uv sync ..."
  (cd backend && uv sync)
fi
if [ ! -d "frontend/node_modules" ]; then
  echo "[setup] npm install ..."
  (cd frontend && npm install)
fi

# --- 启动 ---
echo "[start] backend  → http://127.0.0.1:8765"
echo "[start] frontend → http://localhost:5173"

# 后端
( cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8765 ) &
BACKEND_PID=$!

# 前端
( cd frontend && npm run dev ) &
FRONTEND_PID=$!

# Ctrl+C 一起收
cleanup() {
  echo ""
  echo "[stop] killing backend ($BACKEND_PID) and frontend ($FRONTEND_PID)"
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup INT TERM

wait
