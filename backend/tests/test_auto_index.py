"""单章自动 extract_plot 测试。

ai_client.complete 用 monkeypatch 替成同步桩,避免真发起网络请求。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)


def _make_chapter_with_content(client: TestClient, content: str = "这是测试正文。") -> int:
    pr = client.post("/api/projects", json={"name": f"自动索引-{next(_name_seq)}"})
    pid = pr.json()["id"]
    cr = client.post(f"/api/projects/{pid}/chapters", json={"title": "首章"})
    cid = cr.json()["id"]
    if content:
        client.put(f"/api/chapters/{cid}/content", json={"content": content})
    return cid


def _stub_complete(payload: str):
    async def _fn(*args, **kwargs):
        return payload
    return _fn


def test_auto_index_extracts_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter_with_content(client, "男主路遇刺客,激战脱险后躲进废宅。" * 5)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"events": ['
            '{"title": "路遇刺客", "description": "山道遭袭", "character_ids": [], "importance": 4},'
            '{"title": "脱险藏身", "description": "重伤躲进废宅", "character_ids": [], "importance": 3}'
            ']}'
        ),
    )
    r = client.post(f"/api/chapters/{cid}/auto-index")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["extracted"] == 2
    assert data["skipped"] is False

    # 工程级事件列表里能看到这两条
    pid = client.get(f"/api/chapters/{cid}").json()["project_id"]
    events = client.get(f"/api/projects/{pid}/plot/events").json()
    assert len(events) == 2
    assert {e["title"] for e in events} == {"路遇刺客", "脱险藏身"}


def test_auto_index_skips_empty_chapter(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 空正文章节,extract_plot 会 skip 掉,extracted=0
    cid = _make_chapter_with_content(client, "")

    # 即便 stub 设了也不会被调用
    called = False

    async def _fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        return ""

    monkeypatch.setattr(ai_client_module, "complete", _fail_if_called)
    r = client.post(f"/api/chapters/{cid}/auto-index")
    assert r.status_code == 200
    assert r.json() == {"extracted": 0, "skipped": True}
    assert not called


def test_auto_index_replaces_existing_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """auto-index 是「全删重抽」,旧事件应被替换。这是已知 trade-off,
    但本测试明确验证语义,免得后续重构悄悄改了。"""
    cid = _make_chapter_with_content(client, "本章正文" * 20)
    pid = client.get(f"/api/chapters/{cid}").json()["project_id"]

    # 先手动加一条事件
    client.post(
        f"/api/projects/{pid}/plot/events",
        json={"chapter_id": cid, "title": "旧事件", "importance": 3},
    )
    assert len(client.get(f"/api/projects/{pid}/plot/events").json()) == 1

    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"events": [{"title": "新事件", "description": "", "character_ids": [], "importance": 3}]}'
        ),
    )
    r = client.post(f"/api/chapters/{cid}/auto-index")
    assert r.status_code == 200
    assert r.json()["extracted"] == 1

    titles = [e["title"] for e in client.get(f"/api/projects/{pid}/plot/events").json()]
    assert titles == ["新事件"]


def test_auto_index_unknown_chapter_404(client: TestClient) -> None:
    r = client.post("/api/chapters/99999/auto-index")
    assert r.status_code == 404
