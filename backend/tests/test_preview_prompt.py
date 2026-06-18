"""prompt 预览测试:不调 LLM,只验证组装出的 messages 内容。"""

from fastapi.testclient import TestClient


def _setup_full_project(client: TestClient) -> int:
    """造个含总纲、主线、章节梗概的工程,prompt 才有东西可看。"""
    pid = client.post(
        "/api/projects",
        json={
            "name": "预览测试",
            "synopsis": "少年得宝物,登天阶,守护人间。",
            "genre": "玄幻",
        },
    ).json()["id"]
    client.post(
        f"/api/projects/{pid}/threads",
        json={"title": "复仇线", "description": "灭门之仇", "status": "active"},
    )
    cid = client.post(
        f"/api/projects/{pid}/chapters", json={"title": "首章"}
    ).json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": "已有正文" * 20})
    client.patch(
        f"/api/chapters/{cid}",
        json={
            "summary": "本章发生 X",
            "beats": [{"title": "拍 1", "detail": "AAA"}],
        },
    )
    return cid


def test_preview_generate_includes_synopsis_threads_beats(client: TestClient) -> None:
    cid = _setup_full_project(client)
    r = client.post(
        f"/api/chapters/{cid}/ai/preview-prompt",
        json={"mode": "generate", "target_word_count": 4000},
    )
    assert r.status_code == 200, r.text
    msgs = r.json()["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    user = msgs[1]["content"]
    # 关键块都得在
    assert "少年得宝物" in user  # synopsis
    assert "复仇线" in user  # active thread
    assert "拍 1" in user  # beats
    assert "4000" in user  # target_word_count


def test_preview_continue_includes_cursor_text(client: TestClient) -> None:
    cid = _setup_full_project(client)
    r = client.post(
        f"/api/chapters/{cid}/ai/preview-prompt",
        json={"mode": "continue", "cursor_text": "我刚写到这里。"},
    )
    assert r.status_code == 200
    user = r.json()["messages"][1]["content"]
    assert "我刚写到这里。" in user


def test_preview_rewrite_includes_selection_and_instruction(client: TestClient) -> None:
    cid = _setup_full_project(client)
    r = client.post(
        f"/api/chapters/{cid}/ai/preview-prompt",
        json={
            "mode": "rewrite",
            "selection": "原文片段 ABC",
            "instruction": "改得更紧凑",
        },
    )
    assert r.status_code == 200
    user = r.json()["messages"][1]["content"]
    assert "原文片段 ABC" in user
    assert "改得更紧凑" in user


def test_preview_does_not_call_llm(
    client: TestClient, monkeypatch
) -> None:
    """预览必须跟 LLM 完全无关 —— 桩调用应该不被触发。"""
    from app.ai import client as ai_client_module

    async def _fail(*a, **kw):
        raise AssertionError("LLM should not be called for preview")

    monkeypatch.setattr(ai_client_module, "complete", _fail)
    monkeypatch.setattr(ai_client_module, "stream_chat", _fail)

    cid = _setup_full_project(client)
    r = client.post(
        f"/api/chapters/{cid}/ai/preview-prompt",
        json={"mode": "generate"},
    )
    assert r.status_code == 200


def test_preview_invalid_mode_400(client: TestClient) -> None:
    cid = _setup_full_project(client)
    r = client.post(
        f"/api/chapters/{cid}/ai/preview-prompt",
        json={"mode": "wat"},
    )
    assert r.status_code == 422  # pydantic 在 schema 层就挡掉了


def test_preview_unknown_chapter_404(client: TestClient) -> None:
    r = client.post(
        "/api/chapters/99999/ai/preview-prompt",
        json={"mode": "generate"},
    )
    assert r.status_code == 404
