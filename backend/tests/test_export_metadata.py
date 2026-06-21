"""metadata.json / kdp_listing.txt 副产物。"""

import json

from fastapi.testclient import TestClient


def _seed(client: TestClient) -> int:
    return client.post(
        "/api/projects",
        json={
            "name": "副产物测试",
            "pen_name": "Alex Wang",
            "series_name": "Test Series",
            "series_index": 1,
            "blurb": "A description.",
            "keywords": ["a", "b", "c", "d", "e", "f", "g", "h"],
            "categories": ["Fantasy", "Action", "Adventure"],
        },
    ).json()["id"]


def test_export_metadata_json(client: TestClient):
    pid = _seed(client)
    r = client.get(f"/api/projects/{pid}/export.metadata.json")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    data = json.loads(r.content)
    assert data["pen_name"] == "Alex Wang"
    assert data["series_name"] == "Test Series"
    assert data["keywords"] == ["a", "b", "c", "d", "e", "f", "g", "h"]
    assert data["categories"] == ["Fantasy", "Action", "Adventure"]
    assert data["stats"]["chapter_count"] == 0


def test_export_kdp_listing(client: TestClient):
    pid = _seed(client)
    r = client.get(f"/api/projects/{pid}/export.kdp-listing.txt")
    assert r.status_code == 200
    text = r.content.decode("utf-8")
    assert "Amazon KDP" in text
    assert "Alex Wang" in text
    assert "Test Series" in text
    # KDP 仅取前 7 关键词,前缀编号 1.~7.
    for n in range(1, 8):
        assert f"{n}. " in text
    # 超量提示
    assert "已配置 8 个" in text
    assert "已配置 3 个" in text


def test_export_metadata_404(client: TestClient):
    assert client.get("/api/projects/9999/export.metadata.json").status_code == 404
    assert client.get("/api/projects/9999/export.kdp-listing.txt").status_code == 404
