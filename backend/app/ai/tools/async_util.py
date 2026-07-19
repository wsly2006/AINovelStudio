"""异步→同步桥。

MCP 工具的函数签名是同步的(FastMCP 拿签名推 inputSchema,同步函数最省事),
但底层的 LLM 客户端 / AI service 是 async。若在运行中的 event loop 里直接
`asyncio.run` 会抛 "cannot be called from a running event loop"(HTTP
transport 就在 loop 里同步调工具)。

统一解法:开一个短命线程跑一个全新的 event loop,把协程灌进去等结果。
stdio / streamable-http / sse 三种 transport 通吃。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_async_blocking(coro: Coroutine[Any, Any, T]) -> T:
    """在独立线程新建 event loop 跑协程,阻塞返回结果。"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(lambda: asyncio.run(coro)).result()
