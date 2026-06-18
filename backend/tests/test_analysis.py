from fastapi.testclient import TestClient


def _setup(client: TestClient) -> tuple[int, int, int]:
    """创建工程 + 1 章 + 2 人物。返回 (pid, cid, char_a_id, char_b_id) 但只解到 3 元组。"""
    pid = client.post("/api/projects", json={"name": "RP"}).json()["id"]
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "C1"}).json()["id"]
    a = client.post(f"/api/projects/{pid}/characters", json={"name": "甲"}).json()["id"]
    b = client.post(f"/api/projects/{pid}/characters", json={"name": "乙"}).json()["id"]
    return pid, cid, a, b


def test_create_relation(client: TestClient) -> None:
    pid, _, a, b = _setup(client)
    r = client.post(
        f"/api/projects/{pid}/relations",
        json={"from_id": a, "to_id": b, "type": "师徒", "description": "甲是乙的师父"},
    )
    assert r.status_code == 201
    assert r.json()["type"] == "师徒"


def test_relation_self_rejected(client: TestClient) -> None:
    pid, _, a, _ = _setup(client)
    r = client.post(f"/api/projects/{pid}/relations", json={"from_id": a, "to_id": a, "type": "T"})
    assert r.status_code == 400


def test_relation_cross_project_rejected(client: TestClient) -> None:
    pid1, _, a, _ = _setup(client)
    pid2 = client.post("/api/projects", json={"name": "其他"}).json()["id"]
    other = client.post(f"/api/projects/{pid2}/characters", json={"name": "外"}).json()["id"]
    r = client.post(
        f"/api/projects/{pid1}/relations",
        json={"from_id": a, "to_id": other, "type": "T"},
    )
    assert r.status_code == 400


def test_relation_update_delete(client: TestClient) -> None:
    pid, _, a, b = _setup(client)
    rid = client.post(
        f"/api/projects/{pid}/relations", json={"from_id": a, "to_id": b, "type": "朋友"}
    ).json()["id"]

    upd = client.patch(f"/api/relations/{rid}", json={"description": "童年好友"})
    assert upd.status_code == 200
    assert upd.json()["description"] == "童年好友"

    assert client.delete(f"/api/relations/{rid}").status_code == 204


def test_plot_event_crud(client: TestClient) -> None:
    pid, cid, a, b = _setup(client)
    r = client.post(
        f"/api/projects/{pid}/plot/events",
        json={
            "chapter_id": cid,
            "title": "对决",
            "description": "甲乙首次交手",
            "character_ids": [a, b],
            "importance": 4,
            "order_in_chapter": 1,
        },
    )
    assert r.status_code == 201
    eid = r.json()["id"]
    assert r.json()["importance"] == 4

    listed = client.get(f"/api/projects/{pid}/plot/events").json()
    assert len(listed) == 1

    upd = client.patch(f"/api/plot/events/{eid}", json={"importance": 5})
    assert upd.status_code == 200
    assert upd.json()["importance"] == 5

    assert client.delete(f"/api/plot/events/{eid}").status_code == 204
    assert client.get(f"/api/projects/{pid}/plot/events").json() == []


def test_plot_event_chapter_must_belong_project(client: TestClient) -> None:
    pid1, _, _, _ = _setup(client)
    pid2 = client.post("/api/projects", json={"name": "PP2"}).json()["id"]
    c2 = client.post(f"/api/projects/{pid2}/chapters", json={"title": "X"}).json()["id"]

    r = client.post(
        f"/api/projects/{pid1}/plot/events",
        json={"chapter_id": c2, "title": "x"},
    )
    assert r.status_code == 400


def test_cascade_delete_with_project(client: TestClient) -> None:
    pid, _, a, b = _setup(client)
    rid = client.post(
        f"/api/projects/{pid}/relations", json={"from_id": a, "to_id": b, "type": "朋友"}
    ).json()["id"]

    assert client.delete(f"/api/projects/{pid}").status_code == 204
    # 关系不能再被列出(项目已删,顺带级联)
    listed = client.get(f"/api/projects/{pid}/relations")
    # 项目不存在,relation list 仍返回 200 + 空(service 不强校验)
    assert listed.status_code == 200
    assert listed.json() == []
    # 通过 patch 验证关系已物理删除
    assert client.patch(f"/api/relations/{rid}", json={}).status_code == 404
