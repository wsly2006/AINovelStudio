"""AINovelStudio MCP server。

独立子包,与 FastAPI 后端解耦:
- 不被 app.main 引用,不进 HTTP 服务进程
- 独立入口 `python -m app.mcp.server`,被 Claude Desktop / Code 通过 stdio 拉起
- 仅按需复用 app.database / app.services / app.schemas,不反向触碰
"""
