"""章节 AI 文风检查接口测试。

跟评分模块同款的桩函数策略,monkeypatch 掉真实的 AI 调用。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)

_GOOD_PAYLOAD = (
    '{"issues": ['
    '{"kind": "套语", "quote": "他的眼神仿佛深邃的星海", '
    '"why": "比喻俗套且空洞", "suggestion": "用具体动作替代空泛比喻"},'
    '{"kind": "排比堆砌", "quote": "风声呼啸,雨声呼啸,心跳声也呼啸", '
    '"why": "三连排比节奏机械", "suggestion": "保留一个意象再延展"}'
    '], "summary": "整体偏 AI 味,主要是比喻俗套与节奏机械。"}'
)


def _make_chapter(client: TestClient) -> int:
    pr = client.post("/api/projects", json={"name": f"风检测试-{next(_name_seq)}"})
    pid = pr.json()["id"]
    cr = client.post(f"/api/projects/{pid}/chapters", json={"title": "首章"})
    cid = cr.json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": "测试正文" * 50})
    return cid


def _stub_complete(payload: str):
    async def _fn(*args, **kwargs):
        return payload
    return _fn


def test_style_check_creates_record(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(_GOOD_PAYLOAD))
    r = client.post(f"/api/chapters/{cid}/style-checks")
    assert r.status_code == 201, r.text
    data = r.json()
    assert len(data["issues"]) == 2
    assert data["issues"][0]["kind"] == "套语"
    assert "星海" in data["issues"][0]["quote"]
    assert "AI 味" in data["summary"]
    assert data["word_count"] > 0
    # P4 新增:每次检查都同步落客观信号
    assert "signals" in data
    assert data["signals"]["char_count"] > 0
    assert data["signals"]["sentence"]["count"] > 0

    lst = client.get(f"/api/chapters/{cid}/style-checks").json()
    assert len(lst) == 1
    assert lst[0]["id"] == data["id"]


def test_style_check_drops_issues_without_quote(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    # 没 quote 的 issue 没法跳转到原文,直接丢掉这条而不是整次失败
    raw = (
        '{"issues": ['
        '{"kind": "套语", "quote": "", "why": "", "suggestion": ""},'
        '{"kind": "套语", "quote": "他的眼神仿佛深邃的星海", '
        '"why": "比喻俗套", "suggestion": "用动作替代"}'
        '], "summary": ""}'
    )
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(raw))
    r = client.post(f"/api/chapters/{cid}/style-checks")
    assert r.status_code == 201
    data = r.json()
    assert len(data["issues"]) == 1
    assert "星海" in data["issues"][0]["quote"]


def test_style_check_normalizes_unknown_kind(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    raw = (
        '{"issues": ['
        '{"kind": "什么奇怪的标签", "quote": "他的眼神仿佛深邃的星海", '
        '"why": "套路", "suggestion": "改"}'
        '], "summary": ""}'
    )
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(raw))
    r = client.post(f"/api/chapters/{cid}/style-checks")
    assert r.status_code == 201
    assert r.json()["issues"][0]["kind"] == "其他"


def test_style_check_handles_empty_issues(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete('{"issues": [], "summary": "全章过关"}'),
    )
    r = client.post(f"/api/chapters/{cid}/style-checks")
    assert r.status_code == 201
    assert r.json()["issues"] == []
    assert r.json()["summary"] == "全章过关"


def test_style_check_handles_markdown_wrapped_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    raw = "好的:\n```json\n" + _GOOD_PAYLOAD + "\n```"
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(raw))
    r = client.post(f"/api/chapters/{cid}/style-checks")
    assert r.status_code == 201
    assert len(r.json()["issues"]) == 2


def test_style_check_unparseable_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    monkeypatch.setattr(
        ai_client_module, "complete", _stub_complete("这根本不是 JSON")
    )
    r = client.post(f"/api/chapters/{cid}/style-checks")
    assert r.status_code == 502


def test_style_check_unknown_chapter_404(client: TestClient) -> None:
    r = client.get("/api/chapters/99999/style-checks")
    assert r.status_code == 404


def test_delete_check_removes_only_that_one(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(_GOOD_PAYLOAD))
    s1 = client.post(f"/api/chapters/{cid}/style-checks").json()
    s2 = client.post(f"/api/chapters/{cid}/style-checks").json()

    r = client.delete(f"/api/chapters/{cid}/style-checks/{s1['id']}")
    assert r.status_code == 204

    remaining = client.get(f"/api/chapters/{cid}/style-checks").json()
    assert [s["id"] for s in remaining] == [s2["id"]]


def test_delete_check_rejects_mismatched_chapter(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c1 = _make_chapter(client)
    c2 = _make_chapter(client)
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(_GOOD_PAYLOAD))
    s = client.post(f"/api/chapters/{c1}/style-checks").json()
    r = client.delete(f"/api/chapters/{c2}/style-checks/{s['id']}")
    assert r.status_code == 404
    assert len(client.get(f"/api/chapters/{c1}/style-checks").json()) == 1
