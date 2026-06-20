"""通用工具注册表。

设计目标:**让工具不绑死在 MCP 上**。
注册表本身不依赖任何 framework — 任何适配器都能消费它:
- MCP server: 把 mcp_safe 的工具挂到 FastMCP
- 未来的自家 agent (LiteLLM tool calling): 把全部工具转成 OpenAI tool schema
- HTTP debug 端点: 直接 JSON 调用

关键 invariant: **被装饰的函数本身不变**,可以直接像普通函数一样 import 和调用,
只是同时被注册到 REGISTRY。这让"装饰即注册"零侵入。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# pre-hook 列表:在 Tool.call() 真正执行 fn 之前依次调用
# 用途:Phase 3 的 env 开关、审计日志、project_id 越权检查等横切关注点
# 一处注册,全部工具受益
_PRE_HOOKS: list[Callable[[Tool, dict[str, Any]], None]] = []


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[..., Any]

    # 是否暴露给外部 MCP client。读工具默认 True;
    # Phase 3 的写工具会在 env 开关关闭时 mcp_safe=False,即从 client 视图里隐藏
    mcp_safe: bool = True

    # 写操作? 自家 agent 在执行前要弹确认; pre-hook 可据此判断是否要建版本快照
    dangerous: bool = False

    # 分类标签,仅用于文档/调试,Phase 3+ 可能用来分组展示
    category: str = "misc"

    def call(self, /, **kwargs: Any) -> Any:
        """带钩子的统一调用入口。适配器层应调这个,不要直接调 self.fn。"""
        for hook in _PRE_HOOKS:
            hook(self, kwargs)
        return self.fn(**kwargs)


# 全局注册表。键是工具名(默认取函数名,可在装饰器里覆盖)
REGISTRY: dict[str, Tool] = {}


def tool(
    *,
    name: str | None = None,
    mcp_safe: bool = True,
    dangerous: bool = False,
    category: str = "misc",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器:把函数注册到 REGISTRY,description 自动取自 docstring。

    被装饰的函数本身不被改写,直接调用行为不变 — 这一层完全是旁路注册。

    用法:
        @tool(category="projects")
        @friendly_errors
        def list_projects() -> list[dict]:
            \"\"\"docstring 会被当作工具描述给 LLM 看。\"\"\"
            ...
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or fn.__name__
        if tool_name in REGISTRY:
            raise RuntimeError(f"重复注册工具: {tool_name}")
        REGISTRY[tool_name] = Tool(
            name=tool_name,
            description=(fn.__doc__ or "").strip(),
            fn=fn,
            mcp_safe=mcp_safe,
            dangerous=dangerous,
            category=category,
        )
        return fn

    return decorator


def register_pre_hook(hook: Callable[[Tool, dict[str, Any]], None]) -> None:
    """注册一个调用前钩子。Phase 3 的 env 开关 / 审计日志会用到。

    钩子签名: (tool, kwargs) -> None。要拒绝调用就抛异常(PermissionError 等)。
    """
    _PRE_HOOKS.append(hook)


def list_tools(*, mcp_safe_only: bool = False) -> list[Tool]:
    """枚举注册的工具,顺序按注册顺序。"""
    items = list(REGISTRY.values())
    if mcp_safe_only:
        items = [t for t in items if t.mcp_safe]
    return items


@dataclass
class _Registered:
    """内部分类摘要,仅给 Phase 3+ 的调试端点用。"""
    by_category: dict[str, list[str]] = field(default_factory=dict)


def summary() -> _Registered:
    """按 category 分组列出已注册工具名,调试用。"""
    out = _Registered()
    for t in REGISTRY.values():
        out.by_category.setdefault(t.category, []).append(t.name)
    return out
