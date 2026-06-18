from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_empty(client: TestClient) -> None:
    r = client.get("/api/projects")
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_list(client: TestClient) -> None:
    r = client.post("/api/projects", json={"name": "测试工程", "description": "简介"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "测试工程"
    assert body["chapter_count"] == 0
    assert body["word_count"] == 0
    assert body["id"] > 0

    r = client.get("/api/projects")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["name"] == "测试工程"


def test_create_duplicate_name(client: TestClient) -> None:
    client.post("/api/projects", json={"name": "重复名"})
    r = client.post("/api/projects", json={"name": "重复名"})
    assert r.status_code == 400


def test_create_empty_name(client: TestClient) -> None:
    r = client.post("/api/projects", json={"name": "   "})
    assert r.status_code == 422


def test_get_not_found(client: TestClient) -> None:
    r = client.get("/api/projects/9999")
    assert r.status_code == 404


def test_update(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "原名"}).json()["id"]
    r = client.patch(f"/api/projects/{pid}", json={"name": "新名", "genre": "科幻"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "新名"
    assert body["genre"] == "科幻"


def test_delete(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "待删"}).json()["id"]
    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204

    r = client.get(f"/api/projects/{pid}")
    assert r.status_code == 404
