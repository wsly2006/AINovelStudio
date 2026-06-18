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
