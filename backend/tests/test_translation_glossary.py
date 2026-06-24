from fastapi.testclient import TestClient


def _create_project(client: TestClient, name: str = "工程G") -> int:
    return client.post("/api/projects", json={"name": name}).json()["id"]


# ── CRUD ──────────────────────────────────────────────


def test_list_glossary_empty(client: TestClient) -> None:
    pid = _create_project(client)
    r = client.get(f"/api/projects/{pid}/glossary")
    assert r.status_code == 200
    assert r.json() == []


def test_create_entry(client: TestClient) -> None:
    pid = _create_project(client)
    r = client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "李慕白",
            "target": "Li Mubai",
            "target_lang": "en-US",
            "entry_type": "person",
            "notes": "音译,姓名分写",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source"] == "李慕白"
    assert body["target"] == "Li Mubai"
    assert body["target_lang"] == "en-US"
    assert body["entry_type"] == "person"
    assert body["locked"] is False


def test_create_entry_minimal(client: TestClient) -> None:
    """target 允许为空(seed 时还没填)"""
    pid = _create_project(client)
    r = client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "金丹", "entry_type": "term"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["target"] == ""
    assert body["target_lang"] == "en-US"


def test_create_entry_invalid_type(client: TestClient) -> None:
    pid = _create_project(client)
    r = client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "X", "entry_type": "ufo"},
    )
    assert r.status_code == 422


def test_create_duplicate_returns_409(client: TestClient) -> None:
    pid = _create_project(client)
    client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "重名", "target_lang": "en-US"},
    )
    r = client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "重名", "target_lang": "en-US"},
    )
    assert r.status_code == 409


def test_create_same_source_different_lang_ok(client: TestClient) -> None:
    """同一中文词在不同目标语下可以共存"""
    pid = _create_project(client)
    a = client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "金丹", "target": "Golden Core", "target_lang": "en-US"},
    )
    b = client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "金丹", "target": "Núcleo Dorado", "target_lang": "es-ES"},
    )
    assert a.status_code == 201
    assert b.status_code == 201


def test_update_entry(client: TestClient) -> None:
    pid = _create_project(client)
    eid = client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "原名", "target": "Original"},
    ).json()["id"]
    r = client.patch(
        f"/api/glossary/{eid}",
        json={"target": "Renamed", "locked": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["target"] == "Renamed"
    assert body["locked"] is True


def test_delete_entry(client: TestClient) -> None:
    pid = _create_project(client)
    eid = client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "X"},
    ).json()["id"]
    assert client.delete(f"/api/glossary/{eid}").status_code == 204
    assert client.get(f"/api/glossary/{eid}").status_code == 404


def test_cascade_delete_with_project(client: TestClient) -> None:
    pid = _create_project(client)
    eid = client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "X"},
    ).json()["id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/glossary/{eid}").status_code == 404


def test_filter_by_lang_and_type(client: TestClient) -> None:
    pid = _create_project(client)
    # 三条:不同语种 / 不同类型
    client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "李慕白", "target_lang": "en-US", "entry_type": "person"},
    )
    client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "金丹", "target_lang": "en-US", "entry_type": "term"},
    )
    client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "李慕白", "target_lang": "es-ES", "entry_type": "person"},
    )

    r = client.get(f"/api/projects/{pid}/glossary?target_lang=en-US")
    assert {it["source"] for it in r.json()} == {"李慕白", "金丹"}

    r = client.get(f"/api/projects/{pid}/glossary?entry_type=person")
    assert all(it["entry_type"] == "person" for it in r.json())
    assert len(r.json()) == 2


def test_404_for_missing(client: TestClient) -> None:
    assert client.get("/api/glossary/9999").status_code == 404
    assert (
        client.patch("/api/glossary/9999", json={"target": "x"}).status_code == 404
    )
    assert client.delete("/api/glossary/9999").status_code == 404
    assert (
        client.get("/api/projects/9999/glossary").status_code == 404
    )


# ── seed ───────────────────────────────────────────


def _seed_fixtures(client: TestClient) -> int:
    """建一个工程 + 几个角色 / 物品 / 世界观条目;返回 project_id。"""
    pid = _create_project(client)
    # characters: 2 个 + 别名
    client.post(
        f"/api/projects/{pid}/characters",
        json={"name": "李慕白", "aliases": ["白爷"]},
    )
    client.post(
        f"/api/projects/{pid}/characters",
        json={"name": "玉娇龙"},
    )
    # items: 1 个 + 别名
    client.post(
        f"/api/projects/{pid}/items",
        json={"name": "青冥剑", "aliases": ["天剑"]},
    )
    # world entities: 1 个 location + 1 个 organization
    client.post(
        f"/api/projects/{pid}/world",
        json={"name": "九华山", "kind": "location"},
    )
    client.post(
        f"/api/projects/{pid}/world",
        json={"name": "武当派", "kind": "organization"},
    )
    return pid


def test_seed_from_project(client: TestClient) -> None:
    pid = _seed_fixtures(client)
    r = client.post(
        f"/api/projects/{pid}/glossary/seed",
        json={"target_lang": "en-US"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # 2 角色 + 2 角色别名(白爷)+ 1 物品 + 1 物品别名(天剑)+ 2 世界观
    # = 李慕白 / 白爷 / 玉娇龙 / 青冥剑 / 天剑 / 九华山 / 武当派 = 7
    assert body["created"] == 7
    assert body["skipped"] == 0
    assert body["updated"] == 0

    listed = client.get(f"/api/projects/{pid}/glossary").json()
    by_source = {it["source"]: it for it in listed}
    assert by_source["李慕白"]["entry_type"] == "person"
    assert by_source["白爷"]["entry_type"] == "person"
    assert by_source["青冥剑"]["entry_type"] == "item"
    assert by_source["九华山"]["entry_type"] == "place"
    assert by_source["武当派"]["entry_type"] == "org"
    # target 全部留空
    assert all(it["target"] == "" for it in listed)


def test_seed_idempotent(client: TestClient) -> None:
    pid = _seed_fixtures(client)
    client.post(
        f"/api/projects/{pid}/glossary/seed",
        json={"target_lang": "en-US"},
    )
    r = client.post(
        f"/api/projects/{pid}/glossary/seed",
        json={"target_lang": "en-US"},
    )
    body = r.json()
    assert body["created"] == 0
    assert body["skipped"] == 7
    # 列表行数不变
    listed = client.get(f"/api/projects/{pid}/glossary").json()
    assert len(listed) == 7


def test_seed_skips_locked_entries(client: TestClient) -> None:
    """locked=True 的行 seed 时不会被改 type"""
    pid = _create_project(client)
    # 先手动建一条 locked,entry_type 故意写错
    eid = client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "李慕白",
            "target": "Li Mubai",
            "entry_type": "other",
            "locked": True,
        },
    ).json()["id"]
    # 再加个角色,seed 时 entry_type 期望被对齐成 person —— 但 locked 拒绝
    client.post(
        f"/api/projects/{pid}/characters",
        json={"name": "李慕白"},
    )
    r = client.post(
        f"/api/projects/{pid}/glossary/seed",
        json={"target_lang": "en-US", "overwrite": True},
    )
    body = r.json()
    assert body["created"] == 0
    assert body["skipped"] == 1

    after = client.get(f"/api/glossary/{eid}").json()
    assert after["entry_type"] == "other"  # locked 没被覆盖
    assert after["target"] == "Li Mubai"


def test_seed_overwrite_realigns_entry_type(client: TestClient) -> None:
    """overwrite=True 时,非 locked 行的 entry_type 会被对齐到来源类型"""
    pid = _create_project(client)
    # 先手动建条目,type 故意错
    eid = client.post(
        f"/api/projects/{pid}/glossary",
        json={"source": "李慕白", "entry_type": "other"},
    ).json()["id"]
    client.post(
        f"/api/projects/{pid}/characters",
        json={"name": "李慕白"},
    )
    r = client.post(
        f"/api/projects/{pid}/glossary/seed",
        json={"target_lang": "en-US", "overwrite": True},
    )
    body = r.json()
    assert body["updated"] == 1
    after = client.get(f"/api/glossary/{eid}").json()
    assert after["entry_type"] == "person"
