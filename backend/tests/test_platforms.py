"""平台 profile 接口验证。"""

from fastapi.testclient import TestClient


def test_list_platforms_returns_eight_presets(client: TestClient):
    r = client.get("/api/platforms")
    assert r.status_code == 200
    data = r.json()
    presets = [p for p in data if p["is_preset"]]
    codes = {p["code"] for p in presets}
    assert codes == {
        "kdp",
        "webnovel",
        "royalroad",
        "wattpad",
        "qidian",
        "fanqie",
        "jjwxc",
        "generic",
    }
    # 关键字段不能丢
    kdp = next(p for p in presets if p["code"] == "kdp")
    assert "epub" in kdp["formats"]
    schema_keys = {f["key"] for f in kdp["metadata_schema"]}
    assert {"pen_name", "blurb", "keywords", "categories"}.issubset(schema_keys)


def test_get_platform_by_id(client: TestClient):
    listing = client.get("/api/platforms").json()
    pid = listing[0]["id"]
    r = client.get(f"/api/platforms/{pid}")
    assert r.status_code == 200
    assert r.json()["id"] == pid


def test_create_user_platform_then_delete(client: TestClient):
    payload = {
        "code": "demo",
        "name": "Demo Platform",
        "region": "other",
        "formats": ["epub", "txt"],
        "chapter_strategy": "both",
        "metadata_schema": [
            {"key": "pen_name", "label": "笔名", "required": True, "type": "text"},
        ],
        "encoding": "utf-8",
        "notes": "test",
    }
    r = client.post("/api/platforms", json=payload)
    assert r.status_code == 201, r.text
    new_id = r.json()["id"]
    assert r.json()["is_preset"] is False

    # 同 code 再 POST 报冲突
    r2 = client.post("/api/platforms", json=payload)
    assert r2.status_code == 400

    # 用户自建可删
    r3 = client.delete(f"/api/platforms/{new_id}")
    assert r3.status_code == 204


def test_preset_cannot_be_deleted(client: TestClient):
    listing = client.get("/api/platforms").json()
    kdp = next(p for p in listing if p["code"] == "kdp")
    r = client.delete(f"/api/platforms/{kdp['id']}")
    assert r.status_code == 400


def test_project_publishing_metadata_round_trip(client: TestClient):
    create = client.post(
        "/api/projects",
        json={
            "name": "海外流水线测试",
            "genre": "xianxia",
            "pen_name": "Alex Wang",
            "series_name": "Sword & Spell",
            "series_index": 1,
            "blurb": "A young cultivator rises.",
            "keywords": ["cultivation", "xianxia", "rebirth"],
            "categories": ["Fantasy", "Action"],
            "target_platform_codes": ["kdp", "webnovel"],
        },
    )
    assert create.status_code == 201, create.text
    pid = create.json()["id"]

    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["pen_name"] == "Alex Wang"
    assert detail["series_name"] == "Sword & Spell"
    assert detail["series_index"] == 1
    assert detail["blurb"].startswith("A young")
    assert detail["keywords"] == ["cultivation", "xianxia", "rebirth"]
    assert detail["categories"] == ["Fantasy", "Action"]
    assert detail["target_platform_codes"] == ["kdp", "webnovel"]

    # PATCH 更新
    upd = client.patch(
        f"/api/projects/{pid}",
        json={"keywords": ["cultivation", "rebirth"], "blurb": "shorter"},
    )
    assert upd.status_code == 200
    assert upd.json()["keywords"] == ["cultivation", "rebirth"]
    assert upd.json()["blurb"] == "shorter"
