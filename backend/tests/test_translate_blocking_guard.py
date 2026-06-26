"""translate_chapter_blocking 的事件循环守卫测试。

P0-M6 加的 MCP 工具 translate_chapter 同步调用 translate_chapter_blocking,
内部用 asyncio.run。这要求当前线程不能已经有运行中的 event loop。
M1 修复后,这条规则被显式守卫;本测试锁住该行为。
"""

import asyncio

import pytest
from sqlalchemy.orm import Session

from app.services import chapter_translation_service


async def test_blocking_raises_when_called_from_running_loop(
    db_session: Session,
) -> None:
    """在 pytest-asyncio 的 event loop 里调 blocking → 立刻 RuntimeError。

    通过显式守卫给出清晰错误,而不是把 asyncio.run 的内部
    "asyncio.run() cannot be called from a running event loop" 暴露给上层。
    """
    # 确认当前真的有运行中的 loop(否则测试本身假设就不成立)
    asyncio.get_running_loop()

    with pytest.raises(RuntimeError) as exc:
        chapter_translation_service.translate_chapter_blocking(
            db_session, chapter_id=1, target_lang="en-US"
        )
    msg = str(exc.value)
    assert "event loop" in msg or "translate_and_persist" in msg
