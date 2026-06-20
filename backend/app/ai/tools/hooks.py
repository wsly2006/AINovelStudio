"""调用前钩子集合。

Phase 3 引入两个核心 hook,通过注册表的 pre-hook 机制生效,
所有工具(尤其 dangerous=True 的写工具)自动受益,无需在工具内部重复:

- gate_writes:看到 dangerous 工具且 env 开关未打开时,直接拒绝
- audit_log:把每次 dangerous 工具调用写到 stderr 日志(stdio 协议是 stdout,
  stderr 安全,不会污染 MCP 协议帧)

env 开关:`AI_NOVEL_MCP_ENABLE_WRITES`(true / 1 / yes 视为启用,其它一律视为关闭)
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from app.ai.tools.registry import Tool, register_pre_hook

# stderr 专用 logger — stdio 模式下严禁打 stdout,这里强制走 stderr
_audit_logger = logging.getLogger("app.ai.tools.audit")
if not _audit_logger.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(
        logging.Formatter("%(asctime)s [AUDIT] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    _audit_logger.addHandler(_h)
    _audit_logger.setLevel(logging.INFO)
    _audit_logger.propagate = False  # 不向 root 冒泡,避免任何 stdout handler 误中


_TRUE_VALUES = {"1", "true", "yes", "on"}


def writes_enabled() -> bool:
    """统一判定写操作 env 开关是否打开。"""
    return os.getenv("AI_NOVEL_MCP_ENABLE_WRITES", "").strip().lower() in _TRUE_VALUES


def gate_writes(t: Tool, kwargs: dict[str, Any]) -> None:
    """env 开关关闭时,任何 dangerous 工具调用都拒绝。

    抛 PermissionError → 适配器层会把它转成对 LLM 友好的错误响应,
    让模型知道"这工具被禁用了,不要重试"。
    """
    if t.dangerous and not writes_enabled():
        raise PermissionError(
            f"工具 {t.name} 是写操作,当前已被环境变量 AI_NOVEL_MCP_ENABLE_WRITES "
            f"禁用。要启用,请在启动 MCP server 前设置 AI_NOVEL_MCP_ENABLE_WRITES=true。"
        )


def audit_log(t: Tool, kwargs: dict[str, Any]) -> None:
    """记录每次 dangerous 工具调用到 stderr。

    只记 dangerous 工具(读工具量大,审计意义不大,要查直接看业务日志)。
    敏感字段不脱敏:这是本地单用户工具,完整调用日志比脱敏后的"半成品"更有用。
    """
    if not t.dangerous:
        return
    # 长字段(content / 大段文本)截断到前 200 字,避免审计日志爆炸
    safe = {}
    for k, v in kwargs.items():
        if isinstance(v, str) and len(v) > 200:
            safe[k] = v[:200] + f"...(+{len(v) - 200} chars)"
        else:
            safe[k] = v
    _audit_logger.info("call %s args=%s", t.name, safe)


def install() -> None:
    """注册全部 Phase 3 钩子。幂等 — 多次调用也只装一次。

    在适配器层启动时调一次:
        from app.ai.tools.hooks import install as install_hooks
        install_hooks()
    """
    if getattr(install, "_done", False):
        return
    register_pre_hook(gate_writes)
    register_pre_hook(audit_log)
    install._done = True  # type: ignore[attr-defined]
