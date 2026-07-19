"""MCP server 入口 — Phase 2 改成消费通用注册表,Phase 3 加上写操作 + 钩子。

启动:
    uv run python -m app.mcp.server                          # 只读模式
    AI_NOVEL_MCP_ENABLE_WRITES=true uv run python -m app.mcp.server   # 启用写工具

约束:
- stdio 协议用 stdout 传协议帧,严禁任何 print 走 stdout
- 后续工具如需日志,统一用 logging(默认走 stderr)或写文件

业务逻辑全在 app.ai.tools 下,跟 MCP 解耦:
- 加载 ORM mapper(共用 app.database._import_all_models)
- 触发 app.ai.tools.* 模块导入,让 @tool 装饰器把工具登记到 REGISTRY
- 安装 pre-hooks(env 开关、审计日志)
- 把 REGISTRY 中 mcp_safe=True 且通过 env 检查的工具挂到 FastMCP 实例
- 暴露一个 ping 工具,用于纯协议链路自检
"""

from __future__ import annotations

from functools import wraps

from mcp.server.fastmcp import FastMCP

from app.ai.tools import (  # noqa: F401  触发 @tool 注册
    chapters,
    characters,
    items,
    outline,
    plot,
    projects,
    relations,
    tasks,
    translation,
    versions,
    world,
    writing,
)
from app.ai.tools.hooks import install as install_hooks
from app.ai.tools.hooks import writes_enabled
from app.ai.tools.registry import REGISTRY, Tool
from app.database import _import_all_models

# 启动 MCP 进程时只需注册 ORM 映射,不跑 create_all / 迁移 — 那是主后端的事
_import_all_models()

# 安装钩子(gate_writes + audit_log)。注册表里的所有工具自动受益
install_hooks()

mcp = FastMCP("ai-novel-studio")


@mcp.tool()
def ping() -> dict:
    """连通性自检。返回固定结构,用来确认 MCP 通道可用。"""
    return {"ok": True, "server": "ai-novel-studio"}


def _bind(t: Tool) -> None:
    """把注册表里的一个工具挂到 FastMCP。

    用 functools.wraps 把原函数的签名/类型注解/docstring 透传给适配器函数,
    这样 FastMCP 才能自动推 inputSchema。函数体内走 t.call() 以便 pre-hook
    生效(env 开关 / 审计日志 / 后续 Phase 的横切关注点)。
    """

    @wraps(t.fn)
    def adapter(**kwargs):
        return t.call(**kwargs)

    mcp.tool(name=t.name, description=t.description)(adapter)


# 把注册表里通过两道闸门的工具暴露出去:
# 闸门 1:mcp_safe=True   — 工具自身允许暴露给外部
# 闸门 2:env 开关        — dangerous 工具仅在显式启用时才进客户端工具列表
# (即便闸门 2 漏放,Tool.call 里的 gate_writes hook 仍会兜底拒绝执行)
_writes_on = writes_enabled()
for _t in REGISTRY.values():
    if not _t.mcp_safe:
        continue
    if _t.dangerous and not _writes_on:
        continue
    _bind(_t)


def main() -> None:
    # 默认保持 stdio — Claude Desktop / Code 通过管道拉起进程,不能改动;
    # 显式指定 --transport streamable-http/sse 时才切到网络监听,给别的客户端连
    import argparse

    parser = argparse.ArgumentParser(prog="app.mcp.server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11889)
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return

    # 网络 transport 要给浏览器里的 MCP Inspector 套 CORS,否则 fetch 直接被拦;
    # mcp-session-id 必须放进 expose_headers,浏览器端才能读到会话头恢复流。
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    mcp.settings.host = args.host
    mcp.settings.port = args.port

    if args.transport == "streamable-http":
        app = mcp.streamable_http_app()
    else:
        app = mcp.sse_app()

    app = CORSMiddleware(
        app,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id"],
    )

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
