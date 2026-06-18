"""章节节拍(beats)+ AI 草拟测试。

ai_client.complete 用 monkeypatch 替成同步桩,避免真发起网络请求。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)


def _make_project_with_chapter(client: TestClient) -> tuple[int, int]:
    pr = client.post("/api/projects", json={
        "name": f"节拍测试-{next(_name_seq)}",
        "synopsis": "少年得宝物,登天阶,最终守护人间。",
    })
    pid = pr.json()["id"]
    cr = client.post(f"/api/projects/{pid}/chapters", json={"title": "首章"})
    cid = cr.json()["id"]
    return pid, cid


def _stub_complete(payload: str):
    async def _fn(*args, **kwargs):
        return payload
    return _fn


# ============ Beats CRUD via PATCH ============


def test_chapter_beats_default_null(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)
    r = client.get(f"/api/chapters/{cid}").json()
    assert r["beats"] is None


def test_chapter_update_persists_beats(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)
    payload = {
        "beats": [
            {"title": "男主路遇刺客", "detail": "刺客认得他面相", "thread_titles": ["复仇线"]},
            {"title": "脱险后回村", "detail": "发现村里又出了事", "thread_titles": []},
        ]
    }
    r = client.patch(f"/api/chapters/{cid}", json=payload)
    assert r.status_code == 200, r.text
    assert len(r.json()["beats"]) == 2
    assert r.json()["beats"][0]["title"] == "男主路遇刺客"

    # 重新拉一次,持久化生效
    again = client.get(f"/api/chapters/{cid}").json()
    assert again["beats"][0]["thread_titles"] == ["复仇线"]


def test_chapter_update_clears_beats_with_empty_array(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)
    client.patch(f"/api/chapters/{cid}", json={"beats": [{"title": "X"}]})
    r = client.patch(f"/api/chapters/{cid}", json={"beats": []})
    assert r.status_code == 200
    assert r.json()["beats"] == []


def test_chapter_beats_validation_strips_blank_title(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)
    r = client.patch(f"/api/chapters/{cid}", json={"beats": [{"title": "   "}]})
    assert r.status_code == 422


# ============ AI 草拟节拍 ============


def test_suggest_beats_returns_validated_list(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cid = _make_project_with_chapter(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"beats": ['
            '{"title": "男主路遇刺客", "detail": "在山道上撞见三名持刀蒙面人", "thread_titles": ["复仇线"]},'
            '{"title": "脱险藏身", "detail": "重伤后躲进废宅,意外发现一本残卷", "thread_titles": []},'
            '{"title": "残卷透露线索", "detail": "卷上提到一个组织的暗号", "thread_titles": ["复仇线"]}'
            ']}'
        ),
    )
    r = client.post(f"/api/chapters/{cid}/ai/suggest-beats", json={"target_word_count": 4000})
    assert r.status_code == 200, r.text
    beats = r.json()["beats"]
    assert len(beats) == 3
    assert beats[0]["title"] == "男主路遇刺客"
    assert beats[0]["thread_titles"] == ["复仇线"]
    assert beats[1]["thread_titles"] == []


def test_suggest_beats_handles_markdown_wrapped_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cid = _make_project_with_chapter(client)
    raw = (
        "好的:\n```json\n"
        '{"beats": [{"title": "X", "detail": "Y", "thread_titles": []}]}'
        "\n```"
    )
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(raw))
    r = client.post(f"/api/chapters/{cid}/ai/suggest-beats", json={})
    assert r.status_code == 200
    assert r.json()["beats"][0]["title"] == "X"


def test_suggest_beats_drops_invalid_items_keeps_valid(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cid = _make_project_with_chapter(client)
    # 一个空 title 的拍要被丢掉,合法的留下
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"beats": ['
            '{"title": "", "detail": "应被丢弃"},'
            '{"title": "正常拍", "detail": "保留"}'
            ']}'
        ),
    )
    r = client.post(f"/api/chapters/{cid}/ai/suggest-beats", json={})
    assert r.status_code == 200
    assert len(r.json()["beats"]) == 1
    assert r.json()["beats"][0]["title"] == "正常拍"


def test_suggest_beats_unparseable_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cid = _make_project_with_chapter(client)
    monkeypatch.setattr(
        ai_client_module, "complete", _stub_complete("这根本不是 JSON")
    )
    r = client.post(f"/api/chapters/{cid}/ai/suggest-beats", json={})
    assert r.status_code == 502


def test_suggest_beats_empty_beats_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cid = _make_project_with_chapter(client)
    monkeypatch.setattr(
        ai_client_module, "complete", _stub_complete('{"beats": []}')
    )
    r = client.post(f"/api/chapters/{cid}/ai/suggest-beats", json={})
    assert r.status_code == 502


def test_suggest_beats_unknown_chapter_404(client: TestClient) -> None:
    r = client.post("/api/chapters/99999/ai/suggest-beats", json={})
    assert r.status_code == 404


# ============ Prompt 注入(关键回归):beats 是否进了 user prompt ============


def test_prompt_injects_beats_into_generate() -> None:
    """build_generate_messages 必须把 chapter.beats 注入 user prompt,且每拍都出现。"""
    from types import SimpleNamespace

    from app.ai import prompts

    project = SimpleNamespace(
        name="X", genre="玄幻", description=None, synopsis=None
    )
    chapter = SimpleNamespace(
        id=1,
        order_index=1,
        title="开篇",
        content="",
        summary=None,
        beats=[
            {"title": "男主路遇刺客", "detail": "认得面相", "thread_titles": ["复仇线"]},
            {"title": "脱险藏身", "detail": "发现残卷", "thread_titles": []},
        ],
    )
    msgs = prompts.build_generate_messages(
        project, chapter, [], target_word_count=4000, db=None
    )
    user_text = msgs[1]["content"]
    assert "本章节拍" in user_text
    assert "男主路遇刺客" in user_text
    assert "脱险藏身" in user_text
    assert "复仇线" in user_text


def test_prompt_omits_beats_block_when_null() -> None:
    """没列节拍的章节,prompt 里不应出现「本章节拍」标题。"""
    from types import SimpleNamespace

    from app.ai import prompts

    project = SimpleNamespace(
        name="X", genre=None, description=None, synopsis=None
    )
    chapter = SimpleNamespace(
        id=1, order_index=1, title="", content="", summary=None, beats=None
    )
    msgs = prompts.build_generate_messages(
        project, chapter, [], target_word_count=3000, db=None
    )
    assert "本章节拍" not in msgs[1]["content"]


def test_prompt_omits_beats_block_when_empty_list() -> None:
    from types import SimpleNamespace

    from app.ai import prompts

    project = SimpleNamespace(
        name="X", genre=None, description=None, synopsis=None
    )
    chapter = SimpleNamespace(
        id=1, order_index=1, title="", content="", summary=None, beats=[]
    )
    msgs = prompts.build_generate_messages(
        project, chapter, [], target_word_count=3000, db=None
    )
    assert "本章节拍" not in msgs[1]["content"]
