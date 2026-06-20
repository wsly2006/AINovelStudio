"""通用工具的 DB session 助手。

注册表里的工具不像 FastAPI 路由能用 Depends 注入,这里给一个简单的上下文管理器。
之前放在 app/mcp/db.py — Phase 2 把工具抽到 app/ai/tools/ 后跟着搬过来,因为
这层助手不再仅供 MCP 适配器使用。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.database import SessionLocal


@contextmanager
def with_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
