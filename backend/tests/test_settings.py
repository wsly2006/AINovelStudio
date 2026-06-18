from fastapi.testclient import TestClient


def test_default_settings(client: TestClient) -> None:
    r = client.get("/api/settings/ai")
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "env"
    assert body["model"]
    assert body["api_key_set"] is False


def test_update_settings(client: TestClient) -> None:
    r = client.put(
        "/api/settings/ai",
        json={
            "provider": "deepseek",
            "model": "deepseek/deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-test-1234",
            "temperature": 0.5,
            "max_tokens": 8192,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "deepseek"
    assert body["model"] == "deepseek/deepseek-chat"
    assert body["api_key_set"] is True
    assert "api_key" not in body  # 永远不返回真实 key

    info = client.get("/api/ai/info").json()
    assert info["configured"] is True
    assert info["model"] == "deepseek/deepseek-chat"
    assert info["provider"] == "deepseek"


def test_keep_existing_key(client: TestClient) -> None:
    client.put(
        "/api/settings/ai",
        json={
            "provider": "qwen",
            "model": "dashscope/qwen-max",
            "api_key": "sk-original",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
    )
    # 再次更新但不带 api_key,且 keep_existing_key=true
    r = client.put(
        "/api/settings/ai",
        json={
            "provider": "qwen",
            "model": "dashscope/qwen-plus",
            "keep_existing_key": True,
            "temperature": 0.8,
            "max_tokens": 4096,
        },
    )
    assert r.status_code == 200
    assert r.json()["api_key_set"] is True
    assert r.json()["model"] == "dashscope/qwen-plus"


def test_clear_key(client: TestClient) -> None:
    client.put(
        "/api/settings/ai",
        json={
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "sk-x",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
    )
    r = client.put(
        "/api/settings/ai",
        json={
            "provider": "env",
            "model": "claude-opus-4-7",
            "api_key": "",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
    )
    assert r.json()["api_key_set"] is False


def test_ollama_no_key_required(client: TestClient) -> None:
    r = client.put(
        "/api/settings/ai",
        json={
            "provider": "ollama",
            "model": "ollama/qwen2.5:14b",
            "base_url": "http://localhost:11434",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
    )
    assert r.status_code == 200
    info = client.get("/api/ai/info").json()
    # ollama 不需要 key,configured 应为 true
    assert info["configured"] is True
    assert info["provider"] == "ollama"


def test_review_default_unconfigured(client: TestClient) -> None:
    body = client.get("/api/settings/ai").json()
    assert body["review_configured"] is False
    assert body["review_model"] is None
    assert body["review_api_key_set"] is False


def test_review_update_and_clear(client: TestClient) -> None:
    # 配上写作模型
    client.put(
        "/api/settings/ai",
        json={
            "provider": "claude",
            "model": "claude-opus-4-7",
            "api_key": "sk-write",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
    )
    # 配审稿模型
    r = client.put(
        "/api/settings/ai/review",
        json={
            "enabled": True,
            "provider": "deepseek",
            "model": "deepseek/deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-review",
            "temperature": 0.3,
            "max_tokens": 2000,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["review_configured"] is True
    assert body["review_model"] == "deepseek/deepseek-chat"
    assert body["review_provider"] == "deepseek"
    assert body["review_api_key_set"] is True
    # 写作字段未受影响
    assert body["model"] == "claude-opus-4-7"
    assert body["api_key_set"] is True

    # enabled=False 应清空所有审稿字段
    r = client.put("/api/settings/ai/review", json={"enabled": False})
    assert r.status_code == 200
    body = r.json()
    assert body["review_configured"] is False
    assert body["review_model"] is None
    assert body["review_api_key_set"] is False
    # 写作字段依旧
    assert body["model"] == "claude-opus-4-7"


def test_review_routes_to_review_model_for_review_scenes(
    client: TestClient, monkeypatch
) -> None:
    """评分 / 文风检查 / 一致性检查走审稿模型。"""
    import app.ai.client as ai_client_module

    # 写作 + 审稿都配齐
    client.put(
        "/api/settings/ai",
        json={
            "provider": "claude",
            "model": "writing-model",
            "api_key": "sk-write",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
    )
    client.put(
        "/api/settings/ai/review",
        json={
            "enabled": True,
            "provider": "deepseek",
            "model": "review-model",
            "api_key": "sk-review",
        },
    )

    # 创建一个章节准备评分
    pid = client.post("/api/projects", json={"name": "审稿路由"}).json()["id"]
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "首"}).json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": "正文" * 50})

    seen_models: list[str] = []

    async def _stub(db, messages, *, scene, **kwargs):
        # 通过 runtime 反推 client 这次实际选了哪个 model
        from app.ai.runtime import resolve, role_for_scene
        cfg = resolve(db, role_for_scene(scene))
        seen_models.append(cfg.model)
        return (
            '{"writing": 8, "plot": 7, "characters": 9, "overall": 8, '
            '"feedback": "ok"}'
        )

    monkeypatch.setattr(ai_client_module, "complete", _stub)

    # 评分 → 审稿模型
    client.post(f"/api/chapters/{cid}/scores")
    assert seen_models[-1] == "review-model"

    # 文风检查 → 审稿模型
    async def _stub_style(db, messages, *, scene, **kwargs):
        from app.ai.runtime import resolve, role_for_scene
        cfg = resolve(db, role_for_scene(scene))
        seen_models.append(cfg.model)
        return '{"issues": [], "summary": "ok"}'
    monkeypatch.setattr(ai_client_module, "complete", _stub_style)
    client.post(f"/api/chapters/{cid}/style-checks")
    assert seen_models[-1] == "review-model"


def test_review_falls_back_to_writing_when_unconfigured(
    client: TestClient, monkeypatch
) -> None:
    """审稿未配置时,评分等场景回落用写作模型。"""
    import app.ai.client as ai_client_module

    client.put(
        "/api/settings/ai",
        json={
            "provider": "claude",
            "model": "writing-model",
            "api_key": "sk-write",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
    )
    # 不配审稿

    pid = client.post("/api/projects", json={"name": "回落"}).json()["id"]
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "首"}).json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": "正文" * 50})

    seen_models: list[str] = []

    async def _stub(db, messages, *, scene, **kwargs):
        from app.ai.runtime import resolve, role_for_scene
        cfg = resolve(db, role_for_scene(scene))
        seen_models.append(cfg.model)
        return (
            '{"writing": 8, "plot": 7, "characters": 9, "overall": 8, '
            '"feedback": "ok"}'
        )

    monkeypatch.setattr(ai_client_module, "complete", _stub)
    client.post(f"/api/chapters/{cid}/scores")
    assert seen_models[-1] == "writing-model"

