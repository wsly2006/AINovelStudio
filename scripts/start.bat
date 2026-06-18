@echo off
rem 一键启动:Windows 原生 cmd / PowerShell 用户双击即可。
rem 会开两个独立窗口分别跑后端和前端,关掉窗口即停。

setlocal
set ROOT=%~dp0..
cd /d "%ROOT%"

where uv >nul 2>nul || ( echo 缺少命令: uv & exit /b 1 )
where npm >nul 2>nul || ( echo 缺少命令: npm & exit /b 1 )

if not exist "backend\.venv" (
  echo [setup] uv sync ...
  pushd backend
  call uv sync || ( popd & exit /b 1 )
  popd
)
if not exist "frontend\node_modules" (
  echo [setup] npm install ...
  pushd frontend
  call npm install || ( popd & exit /b 1 )
  popd
)

echo [start] backend  ^=^> http://127.0.0.1:8765
echo [start] frontend ^=^> http://localhost:5173

start "AI Novel - backend" cmd /k "cd /d %ROOT%\backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8765"
start "AI Novel - frontend" cmd /k "cd /d %ROOT%\frontend && npm run dev"

endlocal
