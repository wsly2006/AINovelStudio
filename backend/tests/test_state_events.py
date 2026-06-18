from fastapi.testclient import TestClient


def _setup(client: TestClient) -> dict:
    """造一份完整工程:1 阶梯 + 3 章 + 1 人物 + 1 物品 + 2 地点。"""
    pid = client.post(
        "/api/projects", json={"name": "S6.2", "genre": "xianxia"}
    ).json()["id"]
    # genre=xianxia 自动建一个修仙阶梯
    ladders = client.get(f"/api/projects/{pid}/ladders").json()
    lid = ladders[0]["id"]

    c1 = client.post(f"/api/projects/{pid}/chapters", json={"title": "第一章"}).json()["id"]
    c2 = client.post(f"/api/projects/{pid}/chapters", json={"title": "第二章"}).json()["id"]
    c3 = client.post(f"/api/projects/{pid}/chapters", json={"title": "第三章"}).json()["id"]

    hid = client.post(
        f"/api/projects/{pid}/characters",
        json={"name": "李逍遥", "ladder_id": lid, "current_tier_index": 0},
    ).json()["id"]

    loc1 = client.post(
        f"/api/projects/{pid}/world", json={"kind": "location", "name": "清风谷"}
    ).json()["id"]
    loc2 = client.post(
        f"/api/projects/{pid}/world", json={"kind": "location", "name": "青云山"}
    ).json()["id"]
    item1 = client.post(
        f"/api/projects/{pid}/items", json={"name": "玄铁剑"}
    ).json()["id"]

    return {
        "pid": pid, "lid": lid, "hid": hid,
        "c1": c1, "c2": c2, "c3": c3,
        "loc1": loc1, "loc2": loc2, "item1": item1,
    }


def test_create_state_event(client: TestClient) -> None:
    s = _setup(client)
    r = client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={
            "chapter_id": s["c2"],
            "kind": "tier_up",
            "payload": {"from_index": 0, "to_index": 1, "note": "破境"},
            "order_in_chapter": 1,
        },
    )
    assert r.status_code == 201
    assert r.json()["kind"] == "tier_up"


def test_chapter_must_belong_project(client: TestClient) -> None:
    s = _setup(client)
    # 在另一个工程建一章,试图引用
    pid2 = client.post("/api/projects", json={"name": "其他"}).json()["id"]
    other_chap = client.post(f"/api/projects/{pid2}/chapters", json={"title": "X"}).json()["id"]

    r = client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={"chapter_id": other_chap, "kind": "other", "payload": {}},
    )
    assert r.status_code == 400


def test_snapshot_replays_events_in_order(client: TestClient) -> None:
    s = _setup(client)
    # 第 1 章:0 → 1 阶
    client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={"chapter_id": s["c1"], "kind": "tier_up",
              "payload": {"from_index": 0, "to_index": 1}},
    )
    # 第 2 章:1 → 2 阶 + 移动到青云山 + 获得玄铁剑
    client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={"chapter_id": s["c2"], "kind": "tier_up",
              "payload": {"to_index": 2}, "order_in_chapter": 1},
    )
    client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={"chapter_id": s["c2"], "kind": "location_change",
              "payload": {"to_id": s["loc2"]}, "order_in_chapter": 2},
    )
    client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={"chapter_id": s["c2"], "kind": "item_acquired",
              "payload": {"item_id": s["item1"]}, "order_in_chapter": 3},
    )
    # 第 3 章:丢了玄铁剑
    client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={"chapter_id": s["c3"], "kind": "item_lost",
              "payload": {"item_id": s["item1"]}},
    )

    # 第 1 章末快照
    snap1 = client.get(
        f"/api/characters/{s['hid']}/snapshot?as_of_chapter_id={s['c1']}"
    ).json()
    assert snap1["tier_index"] == 1
    assert snap1["location_id"] is None
    assert snap1["item_ids"] == []

    # 第 2 章末快照:阶 2,在青云山,有玄铁剑
    snap2 = client.get(
        f"/api/characters/{s['hid']}/snapshot?as_of_chapter_id={s['c2']}"
    ).json()
    assert snap2["tier_index"] == 2
    assert snap2["location_id"] == s["loc2"]
    assert snap2["item_ids"] == [s["item1"]]

    # 第 3 章末:玄铁剑丢了
    snap3 = client.get(
        f"/api/characters/{s['hid']}/snapshot?as_of_chapter_id={s['c3']}"
    ).json()
    assert snap3["tier_index"] == 2
    assert snap3["item_ids"] == []

    # 不指定 as_of:取全部 = 当前
    snap_all = client.get(f"/api/characters/{s['hid']}/snapshot").json()
    assert snap_all["tier_index"] == 2
    assert snap_all["item_ids"] == []


def test_snapshot_no_events_falls_back_to_character_fields(client: TestClient) -> None:
    """没事件时,快照取 Character 表上的初始字段。"""
    s = _setup(client)
    # 人物 current_tier_index=0 在 _setup 时设过
    snap = client.get(f"/api/characters/{s['hid']}/snapshot").json()
    assert snap["tier_index"] == 0
    assert snap["location_id"] is None


def test_character_cache_synced_after_event(client: TestClient) -> None:
    """事件创建后,人物表的 current_tier_index 应被刷新。"""
    s = _setup(client)
    client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={"chapter_id": s["c1"], "kind": "tier_up",
              "payload": {"to_index": 3}},
    )
    c = client.get(f"/api/characters/{s['hid']}").json()
    assert c["current_tier_index"] == 3


def test_filter_by_character(client: TestClient) -> None:
    s = _setup(client)
    h2 = client.post(
        f"/api/projects/{s['pid']}/characters", json={"name": "乙"}
    ).json()["id"]
    client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={"chapter_id": s["c1"], "kind": "other", "payload": {"note": "甲事件"}},
    )
    client.post(
        f"/api/characters/{h2}/state-events",
        json={"chapter_id": s["c1"], "kind": "other", "payload": {"note": "乙事件"}},
    )
    r1 = client.get(
        f"/api/projects/{s['pid']}/state-events?character_id={s['hid']}"
    ).json()
    assert len(r1) == 1
    r2 = client.get(
        f"/api/projects/{s['pid']}/state-events?character_id={h2}"
    ).json()
    assert len(r2) == 1


def test_update_delete_event(client: TestClient) -> None:
    s = _setup(client)
    eid = client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={"chapter_id": s["c1"], "kind": "injury",
              "payload": {"description": "断臂"}},
    ).json()["id"]

    r = client.patch(
        f"/api/state-events/{eid}",
        json={"payload": {"description": "断左臂", "severity": "heavy"}},
    )
    assert r.status_code == 200
    assert r.json()["payload"]["severity"] == "heavy"

    assert client.delete(f"/api/state-events/{eid}").status_code == 204


def test_cascade_delete_with_chapter(client: TestClient) -> None:
    """删章节时,该章节的 state events 也一起删。"""
    s = _setup(client)
    eid = client.post(
        f"/api/characters/{s['hid']}/state-events",
        json={"chapter_id": s["c1"], "kind": "other", "payload": {"note": "x"}},
    ).json()["id"]

    assert client.delete(f"/api/chapters/{s['c1']}").status_code == 204
    # 事件应连带消失
    listed = client.get(
        f"/api/projects/{s['pid']}/state-events?character_id={s['hid']}"
    ).json()
    assert all(ev["id"] != eid for ev in listed)
