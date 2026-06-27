"""作者声音档案接口验证。"""

from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> int:
    r = client.post("/api/projects", json={"name": "voice-profile-test"})
    assert r.status_code in (200, 201)
    return r.json()["id"]


def test_get_returns_null_when_not_set(client: TestClient):
    pid = _create_project(client)
    r = client.get(f"/api/projects/{pid}/voice-profile")
    assert r.status_code == 200
    assert r.json() is None


def test_put_creates_then_updates(client: TestClient):
    pid = _create_project(client)
    r = client.put(
        f"/api/projects/{pid}/voice-profile",
        json={
            "quirks": ["他总爱说'当然了'", "段尾常用半句留白"],
            "style_notes": "偏白描,少形容词堆砌",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["project_id"] == pid
    assert len(data["quirks"]) == 2
    assert "白描" in data["style_notes"]
    first_id = data["id"]

    # 再 PUT 一次应该是 update(同一行,id 不变)
    r2 = client.put(
        f"/api/projects/{pid}/voice-profile",
        json={"quirks": ["new"], "style_notes": None},
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == first_id
    assert r2.json()["quirks"] == ["new"]
    assert r2.json()["style_notes"] is None


def test_quirks_strip_and_dedup_blanks(client: TestClient):
    pid = _create_project(client)
    r = client.put(
        f"/api/projects/{pid}/voice-profile",
        json={"quirks": ["  ok  ", "", "   ", "ok2"], "style_notes": ""},
    )
    assert r.status_code == 200
    assert r.json()["quirks"] == ["ok", "ok2"]


def test_quirks_cap_at_30(client: TestClient):
    pid = _create_project(client)
    r = client.put(
        f"/api/projects/{pid}/voice-profile",
        json={"quirks": [f"q{i}" for i in range(50)]},
    )
    assert r.status_code == 200
    assert len(r.json()["quirks"]) == 30


def test_delete(client: TestClient):
    pid = _create_project(client)
    client.put(f"/api/projects/{pid}/voice-profile", json={"quirks": ["x"]})
    r = client.delete(f"/api/projects/{pid}/voice-profile")
    assert r.status_code == 204
    # 删完再 GET 应该是 null
    r2 = client.get(f"/api/projects/{pid}/voice-profile")
    assert r2.json() is None


def test_delete_when_absent_404(client: TestClient):
    pid = _create_project(client)
    r = client.delete(f"/api/projects/{pid}/voice-profile")
    assert r.status_code == 404


def test_unknown_project_404(client: TestClient):
    r = client.get("/api/projects/9999/voice-profile")
    assert r.status_code == 404
    r2 = client.put("/api/projects/9999/voice-profile", json={"quirks": []})
    assert r2.status_code == 404


def test_build_prompt_fragment_empty_when_no_profile(client: TestClient):
    """边界:没建过 profile 时 build_prompt_fragment 必须返回空串。

    chapter_ai_service 后续直接拼这个字符串,空串才能安全拼接。
    """
    pid = _create_project(client)
    from app.database import SessionLocal
    from app.services import author_voice_service

    db = SessionLocal()
    try:
        assert author_voice_service.build_prompt_fragment(db, pid) == ""
    finally:
        db.close()


def test_build_prompt_fragment_with_content(client: TestClient):
    pid = _create_project(client)
    client.put(
        f"/api/projects/{pid}/voice-profile",
        json={"quirks": ["挂在嘴边的'当然了'"], "style_notes": "白描为主"},
    )
    from app.database import SessionLocal
    from app.services import author_voice_service

    db = SessionLocal()
    try:
        fragment = author_voice_service.build_prompt_fragment(db, pid)
    finally:
        db.close()
    assert "作者声音" in fragment
    assert "白描" in fragment
    assert "当然了" in fragment
