from fastapi.testclient import TestClient


def test_ladder_crud(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "L1"}).json()["id"]

    # 列表初始为空(此 genre 无默认)
    r = client.get(f"/api/projects/{pid}/ladders")
    assert r.status_code == 200
    assert r.json() == []

    # 创建
    r = client.post(
        f"/api/projects/{pid}/ladders",
        json={
            "name": "修仙",
            "description": "传统修真",
            "tiers": ["练气期", "筑基期", "金丹期"],
        },
    )
    assert r.status_code == 201
    lid = r.json()["id"]
    assert r.json()["tiers"] == ["练气期", "筑基期", "金丹期"]

    # 同名拒绝
    r = client.post(f"/api/projects/{pid}/ladders", json={"name": "修仙", "tiers": []})
    assert r.status_code == 400

    # 更新
    r = client.patch(
        f"/api/ladders/{lid}",
        json={"tiers": ["练气期", "筑基期", "金丹期", "元婴期"]},
    )
    assert r.status_code == 200
    assert len(r.json()["tiers"]) == 4

    # 删除
    assert client.delete(f"/api/ladders/{lid}").status_code == 204
    assert client.get(f"/api/ladders/{lid}").status_code == 404


def test_ladder_seeded_by_genre_xianxia(client: TestClient) -> None:
    """genre=xianxia 应自动创建一份默认阶梯,并启用 progression。"""
    pid = client.post(
        "/api/projects", json={"name": "仙侠", "genre": "xianxia"}
    ).json()["id"]

    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["progression_enabled"] is True

    ladders = client.get(f"/api/projects/{pid}/ladders").json()
    assert len(ladders) == 1
    assert ladders[0]["name"] == "修仙阶梯"
    assert "练气期" in ladders[0]["tiers"]


def test_ladder_not_seeded_for_romance(client: TestClient) -> None:
    pid = client.post(
        "/api/projects", json={"name": "言情", "genre": "romance"}
    ).json()["id"]

    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["progression_enabled"] is False
    assert client.get(f"/api/projects/{pid}/ladders").json() == []


def test_character_with_ladder(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "C", "genre": "fantasy"}).json()["id"]
    ladders = client.get(f"/api/projects/{pid}/ladders").json()
    assert len(ladders) >= 1
    lid = ladders[0]["id"]

    r = client.post(
        f"/api/projects/{pid}/characters",
        json={
            "name": "甲",
            "ladder_id": lid,
            "current_tier_index": 2,
        },
    )
    assert r.status_code == 201
    cid = r.json()["id"]
    assert r.json()["ladder_id"] == lid
    assert r.json()["current_tier_index"] == 2

    # 更新到下一阶
    r = client.patch(f"/api/characters/{cid}", json={"current_tier_index": 3})
    assert r.status_code == 200
    assert r.json()["current_tier_index"] == 3


def test_ladder_cascade_with_project(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"name": "X", "genre": "wuxia"}).json()["id"]
    ladders = client.get(f"/api/projects/{pid}/ladders").json()
    lid = ladders[0]["id"]

    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/ladders/{lid}").status_code == 404


def test_progression_explicit_override(client: TestClient) -> None:
    """言情类工程也能手动启用 progression。"""
    pid = client.post(
        "/api/projects",
        json={"name": "现代修仙文", "genre": "romance", "progression_enabled": True},
    ).json()["id"]
    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["progression_enabled"] is True
    # genre 不在预设里,默认阶梯不会自动创建
    assert client.get(f"/api/projects/{pid}/ladders").json() == []


def test_ladder_seeded_by_tag_esper(client: TestClient) -> None:
    """都市 + 异能标签:即使 genre 不是玄幻类,也按 tag 播种异能阶梯。"""
    pid = client.post(
        "/api/projects",
        json={"name": "末世异能文", "genre": "urban", "tags": ["apocalypse", "esper"]},
    ).json()["id"]

    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["progression_enabled"] is True
    assert proj["tags"] == ["apocalypse", "esper"]

    ladders = client.get(f"/api/projects/{pid}/ladders").json()
    assert len(ladders) == 1
    assert ladders[0]["name"] == "异能等级"
    assert "九阶" in ladders[0]["tiers"]


def test_progression_system_explicit_overrides_genre(client: TestClient) -> None:
    """显式选 progression_system 优先于 genre 默认。"""
    # 仙侠工程,但用户改用武道阶梯
    pid = client.post(
        "/api/projects",
        json={"name": "武道仙侠", "genre": "xianxia", "progression_system": "wuxia"},
    ).json()["id"]

    ladders = client.get(f"/api/projects/{pid}/ladders").json()
    assert len(ladders) == 1
    assert ladders[0]["name"] == "武道境界"


def test_progression_system_empty_disables(client: TestClient) -> None:
    """progression_system 传空串 = 显式不启用,即便 genre 是仙侠也不播种。"""
    pid = client.post(
        "/api/projects",
        json={"name": "无体系仙侠", "genre": "xianxia", "progression_system": ""},
    ).json()["id"]

    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["progression_enabled"] is False
    assert client.get(f"/api/projects/{pid}/ladders").json() == []


def test_project_channel_and_tags_round_trip(client: TestClient) -> None:
    """channel/tags 字段创建后能正确返回。"""
    pid = client.post(
        "/api/projects",
        json={
            "name": "频道工程",
            "channel": "female",
            "genre": "romance",
            "tags": ["palace", "rebirth"],
        },
    ).json()["id"]
    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["channel"] == "female"
    assert proj["tags"] == ["palace", "rebirth"]
