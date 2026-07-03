@echo off
rem One-shot launcher: backend + frontend share the current cmd window.
rem Usage: run.bat [backend_port] [frontend_port]
rem   defaults: backend=8765, frontend=5173
rem Press Ctrl+C to stop the frontend; a best-effort taskkill cleans up the backend.

setlocal
set ROOT=%~dp0..
cd /d "%ROOT%"

set BACKEND_PORT=%1
if "%BACKEND_PORT%"=="" set BACKEND_PORT=8765
set FRONTEND_PORT=%2
if "%FRONTEND_PORT%"=="" set FRONTEND_PORT=5173

where uv >nul 2>nul || ( echo Missing command: uv & exit /b 1 )
where npm >nul 2>nul || ( echo Missing command: npm & exit /b 1 )

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

echo [start] backend  =^> http://127.0.0.1:%BACKEND_PORT%
echo [start] frontend =^> http://localhost:%FRONTEND_PORT%
echo [hint]  press Ctrl+C to stop; both services share this window

rem Backend runs in background, sharing this console's stdout.
start /b "" cmd /c "cd /d %ROOT%\backend && uv run uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT%"

rem Frontend runs in the foreground. Vite reads BACKEND_PORT/FRONTEND_PORT from env.
pushd frontend
call npm run dev
popd

echo.
echo [stop] cleaning up backend on port %BACKEND_PORT% ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING"') do (
  taskkill /F /PID %%p >nul 2>nul
)

endlocal
