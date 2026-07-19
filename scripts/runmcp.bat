@echo off
rem Start the MCP server over a network transport so external clients can connect.
rem Usage: runmcp.bat [port] [transport] [host]
rem   defaults: port=11889  transport=streamable-http  host=127.0.0.1
rem Client URLs:
rem   streamable-http -> http://host:port/mcp
rem   sse             -> http://host:port/sse
rem Pass host=0.0.0.0 to accept LAN clients (add your own auth before exposing).

setlocal
set ROOT=%~dp0..
cd /d "%ROOT%"

rem Enable write-capable MCP tools (update_*, generate_chapter_content, ...).
rem Comment out to run the server in read-only mode.
set AI_NOVEL_MCP_ENABLE_WRITES=true

set MCP_PORT=%1
if "%MCP_PORT%"=="" set MCP_PORT=11889
set MCP_TRANSPORT=%2
if "%MCP_TRANSPORT%"=="" set MCP_TRANSPORT=streamable-http
set MCP_HOST=%3
if "%MCP_HOST%"=="" set MCP_HOST=127.0.0.1

where uv >nul 2>nul || ( echo Missing command: uv & exit /b 1 )

if not exist "backend\.venv" (
  echo [setup] uv sync ...
  pushd backend
  call uv sync || ( popd & exit /b 1 )
  popd
)

echo [start] mcp %MCP_TRANSPORT% =^> http://%MCP_HOST%:%MCP_PORT%
echo [hint]  press Ctrl+C to stop

pushd backend
uv run python -m app.mcp.server --transport %MCP_TRANSPORT% --host %MCP_HOST% --port %MCP_PORT%
popd

endlocal
