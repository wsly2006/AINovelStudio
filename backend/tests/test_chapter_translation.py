"""章节翻译 M3 测试。

stream_chat 用 monkeypatch 替成同步桩;落库走真 chapter_versions。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)


def _create_chapter_with_content(
    client: TestClient, content: str = "第一章正文,主角下山。"
) -> tuple[int, int]:
    pid = client.post(
        "/api/projects", json={"name": f"翻译-{next(_name_seq)}"}
    ).json()["id"]
    cid = client.post(
        f"/api/projects/{pid}/chapters", json={"title": "首章"}
    ).json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": content})
    return pid, cid


def _stub_stream(deltas: list[str]):
    async def _fn(*args, **kwargs):
        for d in deltas:
            yield d

    return _fn


def _capture_messages():
    captured: list[list[dict]] = []

    async def _fn(db, messages, **kwargs):
        captured.append(messages)
        # 翻 5 个 chunk,模拟流式
        for d in ["Li ", "Mubai ", "left ", "the ", "mountain."]:
            yield d

    return captured, _fn


def _consume_sse(client: TestClient, cid: int, body: dict | None = None) -> str:
    with client.stream(
        "POST",
        f"/api/chapters/{cid}/translate",
        json=body or {"target_lang": "en-US"},
    ) as r:
        assert r.status_code == 200, r.read()
        return b"".join(r.iter_bytes()).decode()


def test_translate_streams_and_persists(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, cid = _create_chapter_with_content(
        client, "李慕白下山,与张飞相遇于山道。"
    )

    monkeypatch.setattr(
        ai_client_module,
        "stream_chat",
        _stub_stream(["Li Mubai ", "descended ", "the mountain."]),
    )
    body = _consume_sse(client, cid)

    assert "event: start" in body
    assert "event: delta" in body
    assert "event: done" in body
    # 译文片段都通过 delta 推过来
    assert "Li Mubai" in body
    assert "descended" in body

    # 落库:list 该章节的 en-US 版本应有 1 条
    versions = client.get(
        f"/api/chapters/{cid}/versions?lang=en-US"
    ).json()
    assert len(versions) == 1
    v = versions[0]
    assert v["lang"] == "en-US"
    assert v["reason"] == "translated"
    assert "AI 翻译" in (v["label"] or "")

    # 详情拿到完整译文
    detail = client.get(
        f"/api/chapters/{cid}/versions/{v['id']}"
    ).json()
    assert detail["content"] == "Li Mubai descended the mountain."
    # word_count 是按 _count_words(英文按空格切)算的
    assert detail["word_count"] >= 4


def test_translate_uses_glossary_in_prompt(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """术语表里有「李慕白 → Li Mubai」时,prompt 必须含这一条对照"""
    pid, cid = _create_chapter_with_content(
        client, "李慕白与玉娇龙在山顶交手。"
    )
    # 加两条 glossary,一条带 target,一条空 target —— 空的应被 prompt 过滤掉
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "李慕白",
            "target": "Li Mubai",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "玉娇龙",
            "target": "",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )

    captured, fn = _capture_messages()
    monkeypatch.setattr(ai_client_module, "stream_chat", fn)
    _consume_sse(client, cid)

    assert len(captured) == 1
    msgs = captured[0]
    # system + user 两条
    assert len(msgs) == 2
    blob = msgs[0]["content"] + "\n" + msgs[1]["content"]
    assert "李慕白 → Li Mubai" in blob
    # 空 target 的「玉娇龙 →」不应混进对照表
    assert "玉娇龙 → " not in blob


def test_translate_trim_per_lang(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """连翻 6 次 → en-US 只保留 5 条;手动建的 zh-CN 版本不被挤掉"""
    pid, cid = _create_chapter_with_content(
        client, "原文。" * 30
    )
    monkeypatch.setattr(
        ai_client_module,
        "stream_chat",
        _stub_stream(["English ", "translation."]),
    )
    # 先建一条 zh-CN 手动快照(上限 5)
    client.post(
        f"/api/chapters/{cid}/versions", json={"label": "原文备份"}
    )

    for _ in range(6):
        _consume_sse(client, cid)

    en_versions = client.get(
        f"/api/chapters/{cid}/versions?lang=en-US"
    ).json()
    assert len(en_versions) == 5

    # zh-CN 那条手动版本仍然在
    zh_versions = client.get(
        f"/api/chapters/{cid}/versions?lang=zh-CN"
    ).json()
    assert any(
        v["reason"] == "manual" and v["label"] == "原文备份"
        for v in zh_versions
    )


def test_translate_empty_content_errors(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, cid = _create_chapter_with_content(client, "")

    called = False

    async def _fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        if False:
            yield ""  # 让它是 async generator,但永不进循环

    monkeypatch.setattr(ai_client_module, "stream_chat", _fail_if_called)
    body = _consume_sse(client, cid)
    assert "event: error" in body
    assert "本章正文为空" in body
    assert not called

    # 无版本被写入
    versions = client.get(
        f"/api/chapters/{cid}/versions?lang=en-US"
    ).json()
    assert versions == []


def test_translate_unknown_chapter_streams_error(client: TestClient) -> None:
    body = _consume_sse(client, 99999)
    assert "event: error" in body
    assert "章节不存在" in body


def test_restore_translated_version_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """en-US 版本不允许 restore 回 chapter.content(中文是真相)"""
    pid, cid = _create_chapter_with_content(
        client, "李慕白下山。"
    )
    monkeypatch.setattr(
        ai_client_module,
        "stream_chat",
        _stub_stream(["Li Mubai descends."]),
    )
    _consume_sse(client, cid)

    en_v = client.get(
        f"/api/chapters/{cid}/versions?lang=en-US"
    ).json()[0]
    r = client.post(
        f"/api/chapters/{cid}/versions/{en_v['id']}/restore"
    )
    assert r.status_code == 400
    # chapter.content 仍然是中文
    chap = client.get(f"/api/chapters/{cid}").json()
    assert chap["content"] == "李慕白下山。"
