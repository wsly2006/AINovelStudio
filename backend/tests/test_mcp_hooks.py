"""MCP 钩子层测试。

覆盖 Phase 3 引入的:
- gate_writes:dangerous 工具在 env 开关关闭时拒绝调用
- writes_enabled:env 解析的真值判定

注:hooks 是全局单例,install() 幂等;这里调一次即可。
"""

from __future__ import annotations

import pytest

from app.ai.tools.hooks import gate_writes, install, writes_enabled
from app.ai.tools.registry import REGISTRY, Tool


def _fake_tool(*, dangerous: bool) -> Tool:
    """构造一个独立的 Tool 实例,不入注册表,避免污染。"""
    return Tool(
        name="__fake_tool__",
        description="",
        fn=lambda **kw: kw,
        dangerous=dangerous,
    )


def test_writes_enabled_true_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for v in ["true", "TRUE", "1", "yes", "on", "  True  "]:
        monkeypatch.setenv("AI_NOVEL_MCP_ENABLE_WRITES", v)
        assert writes_enabled() is True, f"value {v!r} should enable writes"


def test_writes_enabled_false_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for v in ["", "false", "0", "no", "off", "maybe"]:
        monkeypatch.setenv("AI_NOVEL_MCP_ENABLE_WRITES", v)
        assert writes_enabled() is False, f"value {v!r} should NOT enable writes"


def test_writes_enabled_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_NOVEL_MCP_ENABLE_WRITES", raising=False)
    assert writes_enabled() is False


def test_gate_writes_blocks_dangerous_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_NOVEL_MCP_ENABLE_WRITES", "false")
    with pytest.raises(PermissionError) as exc:
        gate_writes(_fake_tool(dangerous=True), {})
    assert "AI_NOVEL_MCP_ENABLE_WRITES" in str(exc.value)


def test_gate_writes_allows_dangerous_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_NOVEL_MCP_ENABLE_WRITES", "true")
    # 不抛即通过
    gate_writes(_fake_tool(dangerous=True), {})


def test_gate_writes_ignores_safe_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    """读工具无论 env 是什么都不应被拦截。"""
    monkeypatch.setenv("AI_NOVEL_MCP_ENABLE_WRITES", "false")
    gate_writes(_fake_tool(dangerous=False), {})
    monkeypatch.setenv("AI_NOVEL_MCP_ENABLE_WRITES", "true")
    gate_writes(_fake_tool(dangerous=False), {})


def test_registered_dangerous_tool_call_path_gated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """端到端:Tool.call() 走完所有 pre-hook,gate_writes 应当先于业务函数生效。

    取一个真实的 dangerous 工具,验证 env 关闭时 call() 抛 PermissionError、
    且不进到 fn —— 这是 hook 真正起作用的证据。
    """
    # 触发 translation 工具模块导入,把 @tool 装饰器登记到 REGISTRY
    from app.ai.tools import translation as _translation  # noqa: F401

    install()  # 幂等,确保 gate_writes 已注册到 _PRE_HOOKS
    monkeypatch.setenv("AI_NOVEL_MCP_ENABLE_WRITES", "false")

    # 找一个已注册的 dangerous 工具(translate_chapter 是 P0-M6 引入的写工具)
    tool = REGISTRY["translate_chapter"]
    assert tool.dangerous is True

    # 用 sentinel 验证 fn 没被调用
    called = {"flag": False}
    original_fn = tool.fn

    def _spy(**kwargs):
        called["flag"] = True
        return original_fn(**kwargs)

    monkeypatch.setattr(tool, "fn", _spy)

    with pytest.raises(PermissionError):
        tool.call(chapter_id=1, target_lang="en-US")
    assert called["flag"] is False, "gate_writes 应在 fn 之前拒绝调用"
