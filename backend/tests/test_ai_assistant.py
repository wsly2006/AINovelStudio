"""AI 助手会话接口测试:CRUD + 上下文注入 + SSE 流。"""

from collections.abc import AsyncGenerator
from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)


def _make_project(client: TestClient) -> int:
    r = client.post(
        "/api/projects",
        json={
            "name": f"助手测试-{next(_name_seq)}",
            "synopsis": "少年得宝物,登天阶,守护人间。",
            "genre": "玄幻",
        },
    )
    return r.json()["id"]


def _make_chapter(client: TestClient, pid: int, content: str = "正文片段") -> int:
    cr = client.post(f"/api/projects/{pid}/chapters", json={"title": "首章"})
    cid = cr.json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": content})
    return cid


def _stub_stream(parts: list[str]):
    async def _fn(*args, **kwargs) -> AsyncGenerator[str, None]:
        for p in parts:
            yield p
    return _fn


# ---------- 会话 CRUD ----------


def test_create_and_list_conversation(client: TestClient) -> None:
    pid = _make_project(client)
    r = client.post(
        f"/api/projects/{pid}/ai/conversations", json={"title": "灵感卡"}
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "灵感卡"
    assert data["project_id"] == pid
    assert data["message_count"] == 0

    lst = client.get(f"/api/projects/{pid}/ai/conversations").json()
    assert len(lst) == 1
    assert lst[0]["id"] == data["id"]


def test_create_conversation_default_title(client: TestClient) -> None:
    pid = _make_project(client)
    r = client.post(f"/api/projects/{pid}/ai/conversations", json={})
    assert r.status_code == 201
    assert r.json()["title"] == "新对话"


def test_create_conversation_unknown_project_404(client: TestClient) -> None:
    r = client.post("/api/projects/9999/ai/conversations", json={})
    assert r.status_code == 404


def test_update_conversation_title(client: TestClient) -> None:
    pid = _make_project(client)
    cid = client.post(
        f"/api/projects/{pid}/ai/conversations", json={}
    ).json()["id"]
    r = client.patch(
        f"/api/ai/conversations/{cid}", json={"title": "改名了"}
    )
    assert r.status_code == 200
    assert r.json()["title"] == "改名了"


def test_delete_conversation(client: TestClient) -> None:
    pid = _make_project(client)
    cid = client.post(
        f"/api/projects/{pid}/ai/conversations", json={}
    ).json()["id"]
    r = client.delete(f"/api/ai/conversations/{cid}")
    assert r.status_code == 204
    lst = client.get(f"/api/projects/{pid}/ai/conversations").json()
    assert lst == []


# ---------- prompt 预览 ----------


def test_preview_prompt_injects_project_chapter_selection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    chid = _make_chapter(client, pid, content="本章正文 ABCDEFG")
    cid = client.post(
        f"/api/projects/{pid}/ai/conversations",
        json={"chapter_id": chid},
    ).json()["id"]

    # 即使预览也不应该走 LLM
    async def _fail(*a, **kw):
        raise AssertionError("LLM should not be called for preview")

    monkeypatch.setattr(ai_client_module, "complete", _fail)
    monkeypatch.setattr(ai_client_module, "stream_chat", _fail)

    r = client.post(
        f"/api/ai/conversations/{cid}/preview-prompt",
        json={
            "content": "帮我把这段写得更紧凑",
            "selection_text": "选中的原文 XYZ",
            "chapter_id": chid,
        },
    )
    assert r.status_code == 200, r.text
    msgs = r.json()["messages"]
    assert msgs[0]["role"] == "system"
    user_text = msgs[-1]["content"]
    assert "少年得宝物" in user_text  # 工程总纲
    assert "本章正文 ABCDEFG" in user_text  # 章节正文
    assert "选中的原文 XYZ" in user_text  # 选区
    assert "帮我把这段写得更紧凑" in user_text  # 用户问题


def test_preview_can_skip_chapter_content(client: TestClient) -> None:
    pid = _make_project(client)
    chid = _make_chapter(client, pid, content="本章正文 ABCDEFG")
    cid = client.post(
        f"/api/projects/{pid}/ai/conversations",
        json={"chapter_id": chid},
    ).json()["id"]
    r = client.post(
        f"/api/ai/conversations/{cid}/preview-prompt",
        json={
            "content": "随便聊聊总纲",
            "include_chapter_content": False,
        },
    )
    assert r.status_code == 200
    user_text = r.json()["messages"][-1]["content"]
    # 章节标签还在,但正文被剔掉
    assert "本章正文 ABCDEFG" not in user_text


# ---------- 流式发送 ----------


def test_send_message_streams_and_persists(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    cid = client.post(
        f"/api/projects/{pid}/ai/conversations", json={}
    ).json()["id"]
    monkeypatch.setattr(
        ai_client_module, "stream_chat", _stub_stream(["Hello, ", "world!"])
    )

    with client.stream(
        "POST",
        f"/api/ai/conversations/{cid}/messages",
        json={"content": "你好"},
    ) as resp:
        assert resp.status_code == 200
        body = b"".join(resp.iter_bytes()).decode("utf-8")

    assert "Hello, " in body
    assert "world!" in body
    assert "event: done" in body

    msgs = client.get(f"/api/ai/conversations/{cid}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "你好"
    assert msgs[1]["content"] == "Hello, world!"

    # 第一条用户消息应自动给会话起标题
    conv = client.get(f"/api/projects/{pid}/ai/conversations").json()[0]
    assert conv["title"] == "你好"
    assert conv["message_count"] == 2


def test_send_message_unknown_conversation_404(client: TestClient) -> None:
    r = client.post(
        "/api/ai/conversations/9999/messages", json={"content": "hi"}
    )
    assert r.status_code == 404


def test_history_replayed_on_subsequent_turn(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """第二轮 send 时,assemble 应把第一轮 user/assistant 当 history 注入。"""
    pid = _make_project(client)
    cid = client.post(
        f"/api/projects/{pid}/ai/conversations", json={}
    ).json()["id"]

    captured: list[list[dict]] = []

    async def _capture_stream(db, messages, **kwargs):
        captured.append(list(messages))
        for d in ["ok"]:
            yield d

    monkeypatch.setattr(ai_client_module, "stream_chat", _capture_stream)

    # 第一轮
    with client.stream(
        "POST",
        f"/api/ai/conversations/{cid}/messages",
        json={"content": "第一问"},
    ) as resp:
        b"".join(resp.iter_bytes())
    # 第二轮
    with client.stream(
        "POST",
        f"/api/ai/conversations/{cid}/messages",
        json={"content": "第二问"},
    ) as resp:
        b"".join(resp.iter_bytes())

    assert len(captured) == 2
    second = captured[1]
    # 第二轮 prompt 必须包含历史的 user / assistant 消息
    roles = [m["role"] for m in second]
    assert roles.count("user") >= 2  # 历史 user + 本轮 user
    assert "assistant" in roles
    contents = [m["content"] for m in second]
    assert any("第一问" in c for c in contents)
    assert any("ok" == c for c in contents)
    assert any("第二问" in c for c in contents)
