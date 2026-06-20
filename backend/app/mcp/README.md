# AINovelStudio MCP Server

把 AINovelStudio 的小说库以 [Model Context Protocol](https://modelcontextprotocol.io)
暴露给 Claude Desktop / Claude Code / Cursor 等 MCP 客户端。配置好后,可以直接在
VS Code 里用自然语言查看和操作小说工程。

## 当前阶段

Phase 0 — **骨架自检**。仅暴露一个 `ping` 工具,用来确认协议通道可用。
真正的业务工具(查询章节、改标题、抽取人物等)从 Phase 1 起逐步加入。

## 与主后端的关系

完全独立:
- 不会被 `app.main` 引入,FastAPI 进程不会启动 MCP server
- 通过独立入口 `python -m app.mcp.server` 由 MCP 客户端拉起
- 只单向复用 `app.database` / `app.services` / `app.schemas`
- 数据库走的是同一个 `data/app.db`,**自家 UI 和 MCP 看到的是同一份数据**

## 启动

```bash
cd backend
uv sync                          # 装 mcp 依赖
uv run python -m app.mcp.server  # 启动 stdio server (会阻塞等客户端连入)
```

直接跑会卡住属于正常 —— stdio 模式等待客户端通过 stdin 发协议帧。

## 自检

用 MCP 官方 inspector 工具调试:

```bash
npx @modelcontextprotocol/inspector uv run python -m app.mcp.server
```

浏览器会打开 inspector,在 Tools 面板调用 `ping`,期望响应:

```json
{"ok": true, "server": "ai-novel-studio"}
```

## Claude Desktop 配置

编辑 Claude Desktop 配置文件:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ai-novel": {
      "command": "uv",
      "args": ["run", "python", "-m", "app.mcp.server"],
      "cwd": "d:/GitHome/github/AINovelStudio/backend"
    }
  }
}
```

重启 Claude Desktop,新对话里输入 `/`,应该能看到 `ai-novel:ping`。

## Claude Code (VS Code) 配置

```bash
claude mcp add ai-novel \
  --command "uv" \
  --args "run" "python" "-m" "app.mcp.server" \
  --cwd "d:/GitHome/github/AINovelStudio/backend"
```

或编辑 `~/.claude.json` 的 `mcpServers` 段,格式同 Claude Desktop。

## 注意事项

- **stdout 不能被污染**:stdio transport 用 stdout 传协议帧,业务代码里禁止 `print()`
  到 stdout。需要日志统一走 `logging`(默认 stderr)或写文件
- **Windows 路径**:配置 JSON 里 `cwd` 用正斜杠 `/` 或转义反斜杠 `\\`
- **冷启动**:每次客户端重启会重启 Python 进程,`uv run` 冷启动约 1-2 秒
