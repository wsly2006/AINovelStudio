from fastapi.testclient import TestClient


def _create_project(client: TestClient, name: str = "WP") -> int:
    return client.post("/api/projects", json={"name": name}).json()["id"]


def test_list_empty(client: TestClient) -> None:
    pid = _create_project(client)
    r = client.get(f"/api/projects/{pid}/world")
    assert r.status_code == 200
    assert r.json() == []


def test_create_entity(client: TestClient) -> None:
    pid = _create_project(client)
    r = client.post(
        f"/api/projects/{pid}/world",
        json={
            "kind": "location",
            "name": "清风谷",
            "aliases": ["小谷"],
            "summary": "主角隐居之地",
            "tags": ["秘境"],
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "location"
    assert body["name"] == "清风谷"


def test_kind_filter(client: TestClient) -> None:
    pid = _create_project(client)
    client.post(f"/api/projects/{pid}/world", json={"kind": "location", "name": "L1"})
    client.post(f"/api/projects/{pid}/world", json={"kind": "organization", "name": "O1"})

    locs = client.get(f"/api/projects/{pid}/world?kind=location").json()
    assert [e["name"] for e in locs] == ["L1"]
    orgs = client.get(f"/api/projects/{pid}/world?kind=organization").json()
    assert [e["name"] for e in orgs] == ["O1"]


def test_unique_per_kind(client: TestClient) -> None:
    """同 project + 同 kind + 同 name 唯一,跨 kind 可同名。"""
    pid = _create_project(client)
    client.post(f"/api/projects/{pid}/world", json={"kind": "location", "name": "青云"})
    # 同 kind 重名 → 400
    r = client.post(f"/api/projects/{pid}/world", json={"kind": "location", "name": "青云"})
    assert r.status_code == 400
    # 不同 kind → OK
    r = client.post(f"/api/projects/{pid}/world", json={"kind": "organization", "name": "青云"})
    assert r.status_code == 201


def test_update_delete(client: TestClient) -> None:
    pid = _create_project(client)
    eid = client.post(
        f"/api/projects/{pid}/world", json={"kind": "concept", "name": "御剑术"}
    ).json()["id"]

    r = client.patch(
        f"/api/world/{eid}", json={"summary": "御剑而行", "tags": ["心法", "传承"]}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == "御剑而行"
    assert body["tags"] == ["心法", "传承"]

    assert client.delete(f"/api/world/{eid}").status_code == 204
    assert client.get(f"/api/world/{eid}").status_code == 404


def test_cascade_delete_with_project(client: TestClient) -> None:
    pid = _create_project(client)
    eid = client.post(
        f"/api/projects/{pid}/world", json={"kind": "concept", "name": "御风诀"}
    ).json()["id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/world/{eid}").status_code == 404


def test_merge_extracted_entity() -> None:
    """单元测试 world_entity_service.merge_extracted_entity。"""
    from app.database import Base, SessionLocal, engine
    from app.models.project import Project
    from app.services import world_entity_service

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        p = Project(name="WX")
        db.add(p)
        db.commit()
        db.refresh(p)

        c1 = world_entity_service.merge_extracted_entity(
            db, p.id, "location",
            {"name": "青云山", "aliases": ["云山"], "summary": "门派所在"},
            chapter_id=None,
        )
        assert c1.name == "青云山"
        assert c1.aliases == ["云山"]

        # 同 kind + 同 name → 合并
        c2 = world_entity_service.merge_extracted_entity(
            db, p.id, "location",
            {"name": "青云山", "aliases": ["大青云"], "summary": "终年积雪"},
            chapter_id=None,
        )
        assert c2.id == c1.id
        assert set(c2.aliases) == {"云山", "大青云"}
        assert "门派所在" in c2.summary
        assert "终年积雪" in c2.summary

        # 不同 kind 同名 → 新建
        c3 = world_entity_service.merge_extracted_entity(
            db, p.id, "organization",
            {"name": "青云山"},
            chapter_id=None,
        )
        assert c3.id != c1.id
        assert c3.kind == "organization"
    finally:
        db.close()


def test_export_import_includes_world(client: TestClient) -> None:
    pid = _create_project(client)
    client.post(f"/api/projects/{pid}/chapters", json={"title": "C1"})
    client.post(
        f"/api/projects/{pid}/world",
        json={"kind": "location", "name": "青云山", "summary": "主峰"},
    )

    exported = client.get(f"/api/projects/{pid}/export.json").json()
    assert "world_entities" in exported
    assert len(exported["world_entities"]) == 1
    assert exported["world_entities"][0]["kind"] == "location"

    files = {
        "file": ("export.json", __import__("json").dumps(exported).encode("utf-8"), "application/json")
    }
    r = client.post("/api/projects/import", files=files)
    assert r.status_code == 201
    new_pid = r.json()["id"]

    new_world = client.get(f"/api/projects/{new_pid}/world").json()
    assert len(new_world) == 1
    assert new_world[0]["name"] == "青云山"
