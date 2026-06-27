"""验证 voice profile 注入到 prompt 中。

走 /preview-prompt 接口而非直接调 stream — 拿到完整 messages 才好断言。
"""

from fastapi.testclient import TestClient


def _setup_project_with_chapter(client: TestClient) -> tuple[int, int]:
    pid = client.post(
        "/api/projects",
        json={"name": "voice-inject-test", "synopsis": "测试用"},
    ).json()["id"]
    cid = client.post(
        f"/api/projects/{pid}/chapters", json={"title": "首章"}
    ).json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": "已有正文" * 5})
    return pid, cid


def test_preview_without_profile_has_no_voice_block(client: TestClient):
    _, cid = _setup_project_with_chapter(client)
    r = client.post(
        f"/api/chapters/{cid}/ai/preview-prompt",
        json={"mode": "generate", "target_word_count": 3000},
    )
    assert r.status_code == 200
    msgs = r.json()["messages"]
    system = msgs[0]["content"]
    assert "作者声音" not in system


def test_preview_generate_includes_voice_profile_in_system(client: TestClient):
    pid, cid = _setup_project_with_chapter(client)
    client.put(
        f"/api/projects/{pid}/voice-profile",
        json={
            "quirks": ["他爱说'当然了'", "段尾常留半句"],
            "style_notes": "偏白描,少形容词",
        },
    )
    r = client.post(
        f"/api/chapters/{cid}/ai/preview-prompt",
        json={"mode": "generate", "target_word_count": 3000},
    )
    assert r.status_code == 200
    msgs = r.json()["messages"]
    system = msgs[0]["content"]
    # 作者声音块在 system message 末尾
    assert "【作者声音】" in system
    assert "当然了" in system
    assert "白描" in system


def test_preview_continue_also_injects(client: TestClient):
    pid, cid = _setup_project_with_chapter(client)
    client.put(
        f"/api/projects/{pid}/voice-profile",
        json={"style_notes": "节奏偏快"},
    )
    r = client.post(
        f"/api/chapters/{cid}/ai/preview-prompt",
        json={"mode": "continue", "cursor_text": "我刚写到这里。"},
    )
    assert r.status_code == 200
    system = r.json()["messages"][0]["content"]
    assert "节奏偏快" in system


def test_preview_rewrite_also_injects(client: TestClient):
    """rewrite 模板首条 message 可能不是 system,验证仍能注入。"""
    pid, cid = _setup_project_with_chapter(client)
    client.put(
        f"/api/projects/{pid}/voice-profile",
        json={"quirks": ["他常说'你看'"]},
    )
    r = client.post(
        f"/api/chapters/{cid}/ai/preview-prompt",
        json={
            "mode": "rewrite",
            "selection": "原句。",
            "instruction": "改紧一点。",
        },
    )
    assert r.status_code == 200
    msgs = r.json()["messages"]
    # 整个 messages 拼起来里面必须能找到 voice 内容
    blob = "\n".join(m.get("content", "") for m in msgs)
    assert "你看" in blob


def test_empty_profile_does_not_inject_empty_block(client: TestClient):
    """profile 行存在但 quirks 空 + style_notes 空,不该硬塞空白块。"""
    pid, cid = _setup_project_with_chapter(client)
    client.put(
        f"/api/projects/{pid}/voice-profile",
        json={"quirks": [], "style_notes": None},
    )
    r = client.post(
        f"/api/chapters/{cid}/ai/preview-prompt",
        json={"mode": "generate", "target_word_count": 3000},
    )
    system = r.json()["messages"][0]["content"]
    assert "【作者声音】" not in system
