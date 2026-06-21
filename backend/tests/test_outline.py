"""大纲模式测试:批量草拟 + 批量落库 + 章节-大纲对账。

ai_client.complete 用 monkeypatch 替成同步桩,避免真发起网络请求。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)


def _make_project(client: TestClient, *, with_chapter: bool = False) -> int:
    pr = client.post(
        "/api/projects",
        json={
            "name": f"大纲测试-{next(_name_seq)}",
            "synopsis": "少年得宝物,登天阶,最终守护人间。",
        },
    )
    pid = pr.json()["id"]
    if with_chapter:
        client.post(f"/api/projects/{pid}/chapters", json={"title": "首章"})
    return pid


def _stub_complete(payload: str):
    async def _fn(*args, **kwargs):
        return payload

    return _fn


# ============ 批量草拟 ============


def test_outline_batch_suggest_returns_validated_drafts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    payload = (
        '{"chapters": ['
        '{"title": "初遇", "summary": "少年捡到一枚旧符,自此命运转弯。",'
        ' "beats": ['
        '{"title": "雨中拾符", "detail": "少年躲雨时发现旧符发烫", "thread_titles": ["复仇线"]},'
        '{"title": "符内异象", "detail": "符里有人影闪烁,似有故事", "thread_titles": []}'
        ']},'
        '{"title": "下山", "summary": "决定下山探寻旧符来历。",'
        ' "beats": ['
        '{"title": "辞别师父", "detail": "师父叮嘱要小心镇上的人", "thread_titles": []}'
        ']}'
        ']}'
    )
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(payload))

    r = client.post(
        f"/api/projects/{pid}/outline/batch-suggest",
        json={"count": 2},
    )
    assert r.status_code == 200, r.text
    drafts = r.json()["drafts"]
    assert len(drafts) == 2
    assert drafts[0]["title"] == "初遇"
    assert drafts[0]["summary"].startswith("少年捡到")
    assert len(drafts[0]["beats"]) == 2
    assert drafts[0]["beats"][0]["thread_titles"] == ["复仇线"]


def test_outline_batch_suggest_drops_empty_chapters(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    # 一个完全空的章节 + 一个 title 为空但有 summary 的章节(应保留)
    payload = (
        '{"chapters": ['
        '{"title": "", "summary": "", "beats": []},'
        '{"title": "", "summary": "有梗概的章节", "beats": []}'
        ']}'
    )
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(payload))

    r = client.post(
        f"/api/projects/{pid}/outline/batch-suggest",
        json={"count": 2},
    )
    assert r.status_code == 200
    drafts = r.json()["drafts"]
    assert len(drafts) == 1
    assert drafts[0]["summary"] == "有梗概的章节"


def test_outline_batch_suggest_handles_markdown_wrapped(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    raw = (
        "好的:\n```json\n"
        '{"chapters": [{"title": "X", "summary": "Y", "beats": []}]}'
        "\n```"
    )
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(raw))
    r = client.post(
        f"/api/projects/{pid}/outline/batch-suggest",
        json={"count": 1},
    )
    assert r.status_code == 200
    assert r.json()["drafts"][0]["title"] == "X"


def test_outline_batch_suggest_unparseable_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    monkeypatch.setattr(
        ai_client_module, "complete", _stub_complete("根本不是 JSON")
    )
    r = client.post(
        f"/api/projects/{pid}/outline/batch-suggest",
        json={"count": 3},
    )
    assert r.status_code == 502


def test_outline_batch_suggest_empty_chapters_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    monkeypatch.setattr(
        ai_client_module, "complete", _stub_complete('{"chapters": []}')
    )
    r = client.post(
        f"/api/projects/{pid}/outline/batch-suggest",
        json={"count": 3},
    )
    assert r.status_code == 502


def test_outline_batch_suggest_unknown_project_404(client: TestClient) -> None:
    r = client.post("/api/projects/99999/outline/batch-suggest", json={"count": 3})
    assert r.status_code == 404


# ============ 批量落库 ============


def test_outline_batch_create_appends_to_end(client: TestClient) -> None:
    pid = _make_project(client, with_chapter=True)
    payload = {
        "drafts": [
            {
                "title": "初遇",
                "summary": "少年得旧符。",
                "beats": [
                    {"title": "雨中拾符", "detail": "符里有人影", "thread_titles": []}
                ],
            },
            {"title": "下山", "summary": "决定下山探寻。", "beats": []},
        ]
    }
    r = client.post(f"/api/projects/{pid}/outline/batch-create", json=payload)
    assert r.status_code == 201, r.text
    chapters = r.json()["chapters"]
    assert len(chapters) == 2
    assert chapters[0]["status"] == "outlined"
    assert chapters[0]["order_index"] == 2  # 在已有 1 章之后
    assert chapters[1]["order_index"] == 3

    # 章节列表应包含原章 + 新建 2 章
    listing = client.get(f"/api/projects/{pid}/chapters").json()
    assert len(listing) == 3

    # 详情应能拿回 beats / summary
    detail = client.get(f"/api/chapters/{chapters[0]['id']}").json()
    assert detail["beats"][0]["title"] == "雨中拾符"
    assert detail["summary"] == "少年得旧符。"


def test_outline_batch_create_unknown_project_404(client: TestClient) -> None:
    r = client.post(
        "/api/projects/99999/outline/batch-create",
        json={"drafts": [{"title": "X", "summary": "Y", "beats": []}]},
    )
    assert r.status_code == 404


# ============ 章节-大纲对账 ============


def test_outline_alignment_returns_per_beat_status(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    cr = client.post(
        f"/api/projects/{pid}/chapters",
        json={"title": "初遇", "summary": "少年得旧符,引来追兵。"},
    )
    cid = cr.json()["id"]
    # 给章节设 beats + content
    client.patch(
        f"/api/chapters/{cid}",
        json={
            "beats": [
                {"title": "雨中拾符", "detail": "少年躲雨拾到旧符", "thread_titles": []},
                {"title": "追兵临门", "detail": "三名黑衣人追至", "thread_titles": []},
            ]
        },
    )
    client.put(
        f"/api/chapters/{cid}/content",
        json={"content": "少年躲雨,在墙角拾到一枚发烫的旧符,符面有古纹。" * 5},
    )

    payload = (
        '{"summary_status": "covered", "summary_note": "正文按梗概兑现",'
        ' "beats": ['
        '{"beat_index": 0, "status": "covered", "note": "拾符场景写到了"},'
        '{"beat_index": 1, "status": "missing", "note": "正文没写到追兵"}'
        '],'
        ' "overall_note": "前半兑现良好,但后半节奏断了"}'
    )
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(payload))

    r = client.post(f"/api/chapters/{cid}/outline-alignment")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary_status"] == "covered"
    assert len(body["beats"]) == 2
    assert body["beats"][1]["status"] == "missing"
    # 计数:summary covered (1) + beats covered (1) + missing (1)
    assert body["covered"] == 2
    assert body["missing"] == 1
    assert body["partial"] == 0


def test_outline_alignment_skips_ai_when_no_outline(client: TestClient) -> None:
    """章节没填 summary 也没列 beats 时,直接返回 missing,不调 AI。"""
    pid = _make_project(client)
    cr = client.post(f"/api/projects/{pid}/chapters", json={"title": "空章"})
    cid = cr.json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": "正文"})

    r = client.post(f"/api/chapters/{cid}/outline-alignment")
    assert r.status_code == 200
    body = r.json()
    assert body["summary_status"] == "missing"
    assert body["beats"] == []


def test_outline_alignment_skips_ai_when_no_content(client: TestClient) -> None:
    """章节正文为空时,所有项 missing,不调 AI。"""
    pid = _make_project(client)
    cr = client.post(
        f"/api/projects/{pid}/chapters",
        json={"title": "未写章", "summary": "本章应发生 X"},
    )
    cid = cr.json()["id"]
    client.patch(
        f"/api/chapters/{cid}",
        json={"beats": [{"title": "拍 1", "detail": "..."}]},
    )

    r = client.post(f"/api/chapters/{cid}/outline-alignment")
    assert r.status_code == 200
    body = r.json()
    assert body["summary_status"] == "missing"
    assert len(body["beats"]) == 1
    assert body["beats"][0]["status"] == "missing"


def test_outline_alignment_unknown_chapter_404(client: TestClient) -> None:
    r = client.post("/api/chapters/99999/outline-alignment")
    assert r.status_code == 404
