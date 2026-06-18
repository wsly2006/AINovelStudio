"""章节 AI 评分接口测试。

ai_client.complete 被 monkeypatch 替成同步的桩函数,避免真的发起网络请求。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)


def _make_chapter(client: TestClient) -> int:
    pr = client.post("/api/projects", json={"name": f"评分测试-{next(_name_seq)}"})
    pid = pr.json()["id"]
    cr = client.post(f"/api/projects/{pid}/chapters", json={"title": "首章"})
    cid = cr.json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": "测试正文" * 50})
    return cid


def _stub_complete(payload: str):
    async def _fn(*args, **kwargs):
        return payload
    return _fn


def test_score_creates_record(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    cid = _make_chapter(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"writing": 8, "plot": 7, "characters": 9, "overall": 8, '
            '"feedback": "总体不错的开局,人物动机清晰。"}'
        ),
    )
    r = client.post(f"/api/chapters/{cid}/scores")
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["writing"] == 8
    assert data["plot"] == 7
    assert data["characters"] == 9
    assert data["overall"] == 8
    assert "总体不错" in data["feedback"]
    assert data["word_count"] > 0

    # 列表里能查到刚才那条
    lst = client.get(f"/api/chapters/{cid}/scores").json()
    assert len(lst) == 1
    assert lst[0]["id"] == data["id"]


def test_score_clamps_out_of_range_values(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    # 模型偶尔会越界打分,夹回 [1,10] 总比报错更友好
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"writing": 12, "plot": 0, "characters": 5, "overall": 6, "feedback": ""}'
        ),
    )
    r = client.post(f"/api/chapters/{cid}/scores")
    assert r.status_code == 201
    data = r.json()
    assert data["writing"] == 10
    assert data["plot"] == 1


def test_score_handles_markdown_wrapped_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    # 模型有时会把 JSON 包在 ```json ... ``` 里,解析器要能抠出来
    raw = (
        "好的,这是评分:\n```json\n"
        '{"writing": 6, "plot": 6, "characters": 6, "overall": 6, "feedback": "中规中矩"}'
        "\n```"
    )
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(raw))
    r = client.post(f"/api/chapters/{cid}/scores")
    assert r.status_code == 201
    assert r.json()["writing"] == 6


def test_score_unparseable_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    monkeypatch.setattr(
        ai_client_module, "complete", _stub_complete("这根本不是 JSON")
    )
    r = client.post(f"/api/chapters/{cid}/scores")
    assert r.status_code == 502


def test_score_unknown_chapter_404(client: TestClient) -> None:
    r = client.get("/api/chapters/99999/scores")
    assert r.status_code == 404


def test_delete_score_removes_only_that_one(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"writing": 5, "plot": 5, "characters": 5, "overall": 5, "feedback": "x"}'
        ),
    )
    s1 = client.post(f"/api/chapters/{cid}/scores").json()
    s2 = client.post(f"/api/chapters/{cid}/scores").json()

    r = client.delete(f"/api/chapters/{cid}/scores/{s1['id']}")
    assert r.status_code == 204

    remaining = client.get(f"/api/chapters/{cid}/scores").json()
    assert [s["id"] for s in remaining] == [s2["id"]]


def test_delete_score_rejects_mismatched_chapter(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    c1 = _make_chapter(client)
    c2 = _make_chapter(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"writing": 5, "plot": 5, "characters": 5, "overall": 5, "feedback": "x"}'
        ),
    )
    s = client.post(f"/api/chapters/{c1}/scores").json()
    r = client.delete(f"/api/chapters/{c2}/scores/{s['id']}")
    assert r.status_code == 404
    # 原章节下还在
    assert len(client.get(f"/api/chapters/{c1}/scores").json()) == 1


def test_chapter_list_includes_latest_overall_score(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _make_chapter(client)
    project_id = client.get(f"/api/chapters/{cid}").json()["project_id"]

    # 评分前列表里 latest_overall_score 应为 None
    pre = client.get(f"/api/projects/{project_id}/chapters").json()
    assert pre[0]["latest_overall_score"] is None

    # 第一次评 7 分
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"writing": 6, "plot": 7, "characters": 8, "overall": 7, "feedback": ""}'
        ),
    )
    client.post(f"/api/chapters/{cid}/scores")

    # 第二次评 9 分,列表应反映最新一次
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"writing": 9, "plot": 9, "characters": 9, "overall": 9, "feedback": ""}'
        ),
    )
    client.post(f"/api/chapters/{cid}/scores")

    after = client.get(f"/api/projects/{project_id}/chapters").json()
    assert after[0]["latest_overall_score"] == 9
