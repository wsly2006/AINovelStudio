@echo off
rem One-shot launcher: backend + frontend share the current cmd window.
rem Press Ctrl+C to stop the frontend; a best-effort taskkill cleans up the backend.
rem Output from both services is interleaved in this single console.

setlocal
set ROOT=%~dp0..
cd /d "%ROOT%"

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

echo [start] backend  =^> http://127.0.0.1:8765
echo [start] frontend =^> http://localhost:5173
echo [hint]  press Ctrl+C to stop; both services share this window

rem Backend runs in background, sharing this console's stdout.
start /b "" cmd /c "cd /d %ROOT%\backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8765"

rem Frontend runs in the foreground.
pushd frontend
call npm run dev
popd

echo.
echo [stop] cleaning up backend on port 8765 ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8765 " ^| findstr "LISTENING"') do (
  taskkill /F /PID %%p >nul 2>nul
)

endlocal
