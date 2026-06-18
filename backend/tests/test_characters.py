from fastapi.testclient import TestClient


def _create_project(client: TestClient, name: str = "工程C") -> int:
    return client.post("/api/projects", json={"name": name}).json()["id"]


def test_list_characters_empty(client: TestClient) -> None:
    pid = _create_project(client)
    r = client.get(f"/api/projects/{pid}/characters")
    assert r.status_code == 200
    assert r.json() == []


def test_create_character(client: TestClient) -> None:
    pid = _create_project(client)
    r = client.post(
        f"/api/projects/{pid}/characters",
        json={
            "name": "李逍遥",
            "aliases": ["逍遥哥哥"],
            "role": "主角",
            "profile": "余杭少年,机缘巧合踏上仙道之路",
            "appearance": "一身白衣,剑眉星目",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "李逍遥"
    assert body["aliases"] == ["逍遥哥哥"]


def test_create_duplicate_name(client: TestClient) -> None:
    pid = _create_project(client)
    client.post(f"/api/projects/{pid}/characters", json={"name": "重名"})
    r = client.post(f"/api/projects/{pid}/characters", json={"name": "重名"})
    assert r.status_code == 400


def test_update_character(client: TestClient) -> None:
    pid = _create_project(client)
    cid = client.post(
        f"/api/projects/{pid}/characters", json={"name": "原名"}
    ).json()["id"]
    r = client.patch(
        f"/api/characters/{cid}",
        json={"name": "新名", "personality": "外冷内热"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "新名"
    assert body["personality"] == "外冷内热"


def test_delete_character(client: TestClient) -> None:
    pid = _create_project(client)
    cid = client.post(f"/api/projects/{pid}/characters", json={"name": "X"}).json()["id"]
    assert client.delete(f"/api/characters/{cid}").status_code == 204
    assert client.get(f"/api/characters/{cid}").status_code == 404


def test_cascade_delete_with_project(client: TestClient) -> None:
    pid = _create_project(client)
    cid = client.post(f"/api/projects/{pid}/characters", json={"name": "X"}).json()["id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/characters/{cid}").status_code == 404


def test_merge_extracted_character() -> None:
    """单元测试 character_service.merge_extracted_character。"""
    from app.database import Base, SessionLocal, engine
    from app.models.project import Project
    from app.services import character_service

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        p = Project(name="单测工程")
        db.add(p)
        db.commit()
        db.refresh(p)

        # 首次插入
        c1 = character_service.merge_extracted_character(
            db,
            p.id,
            {"name": "张三", "aliases": ["小三"], "profile": "学生"},
            chapter_id=None,
        )
        assert c1.name == "张三"
        assert c1.aliases == ["小三"]

        # 同名 → 合并别名 + 追加 profile
        c2 = character_service.merge_extracted_character(
            db,
            p.id,
            {"name": "张三", "aliases": ["三哥"], "profile": "热爱篮球"},
            chapter_id=None,
        )
        assert c2.id == c1.id
        assert set(c2.aliases) == {"小三", "三哥"}
        assert "学生" in c2.profile
        assert "热爱篮球" in c2.profile

        # 用别名命中现有人物
        c3 = character_service.merge_extracted_character(
            db,
            p.id,
            {"name": "三哥", "aliases": [], "background": "出身南方"},
            chapter_id=None,
        )
        assert c3.id == c1.id
        assert "出身南方" in c3.background
    finally:
        db.close()
