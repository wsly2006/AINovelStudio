"""章节版本快照接口的端到端测试。"""

from itertools import count

from fastapi.testclient import TestClient

_name_seq = count(1)


def _make_project_with_chapter(client: TestClient) -> tuple[int, int]:
    pr = client.post("/api/projects", json={"name": f"测试项目-{next(_name_seq)}"})
    pid = pr.json()["id"]
    cr = client.post(f"/api/projects/{pid}/chapters", json={"title": "第一章"})
    cid = cr.json()["id"]
    # 写入初始内容
    client.put(f"/api/chapters/{cid}/content", json={"content": "原始内容 v0"})
    return pid, cid


def test_initial_versions_empty(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)
    r = client.get(f"/api/chapters/{cid}/versions")
    assert r.status_code == 200
    assert r.json() == []


def test_manual_snapshot_records_current_content(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)

    r = client.post(f"/api/chapters/{cid}/versions", json={"label": "节点"})
    assert r.status_code == 201
    body = r.json()
    assert body["reason"] == "manual"
    assert body["label"] == "节点"
    assert body["word_count"] > 0

    # 列表里应该看见这一条
    items = client.get(f"/api/chapters/{cid}/versions").json()
    assert len(items) == 1


def test_ai_snapshot_uses_ai_overwrite_reason(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)
    r = client.post(f"/api/chapters/{cid}/versions/ai-snapshot")
    assert r.status_code == 201
    assert r.json()["reason"] == "ai_overwrite"


def test_versions_capped_at_five_fifo(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)

    # 创建 7 条手动版本,每次先改一下内容(模拟真实流程,内容能区分)
    for i in range(7):
        client.put(f"/api/chapters/{cid}/content", json={"content": f"内容 v{i}"})
        r = client.post(f"/api/chapters/{cid}/versions", json={"label": f"v{i}"})
        assert r.status_code == 201

    items = client.get(f"/api/chapters/{cid}/versions").json()
    assert len(items) == 5
    # 最旧的两条应被淘汰,留下 v2..v6,DESC 排序
    labels = [v["label"] for v in items]
    assert labels == ["v6", "v5", "v4", "v3", "v2"]


def test_restore_writes_back_and_snapshots_current(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)

    # 在 "原始内容 v0" 状态做一次手动快照
    snap = client.post(f"/api/chapters/{cid}/versions", json={"label": "before-edit"}).json()
    snap_id = snap["id"]

    # 改写正文
    client.put(f"/api/chapters/{cid}/content", json={"content": "修改后的新内容"})

    # 还原
    r = client.post(f"/api/chapters/{cid}/versions/{snap_id}/restore")
    assert r.status_code == 200
    assert r.json()["content"] == "原始内容 v0"

    # 章节当前内容确实变了
    cur = client.get(f"/api/chapters/{cid}").json()
    assert cur["content"] == "原始内容 v0"

    # 还原会自动把"修改后的新内容"留为 reason='restore' 的快照
    items = client.get(f"/api/chapters/{cid}/versions").json()
    reasons = [v["reason"] for v in items]
    assert "restore" in reasons
    restore_snap = next(v for v in items if v["reason"] == "restore")
    detail = client.get(
        f"/api/chapters/{cid}/versions/{restore_snap['id']}"
    ).json()
    assert detail["content"] == "修改后的新内容"


def test_restore_rejects_mismatched_chapter(client: TestClient) -> None:
    _, c1 = _make_project_with_chapter(client)
    _, c2 = _make_project_with_chapter(client)

    snap = client.post(f"/api/chapters/{c1}/versions", json={"label": "x"}).json()
    # 用另一个章节的 id 去还原 c1 的版本,应当 404
    r = client.post(f"/api/chapters/{c2}/versions/{snap['id']}/restore")
    assert r.status_code == 404


def test_versions_for_unknown_chapter_404(client: TestClient) -> None:
    r = client.get("/api/chapters/99999/versions")
    assert r.status_code == 404


def test_delete_version_removes_only_that_one(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)

    v1 = client.post(f"/api/chapters/{cid}/versions", json={"label": "v1"}).json()
    v2 = client.post(f"/api/chapters/{cid}/versions", json={"label": "v2"}).json()

    r = client.delete(f"/api/chapters/{cid}/versions/{v1['id']}")
    assert r.status_code == 204

    items = client.get(f"/api/chapters/{cid}/versions").json()
    assert [v["id"] for v in items] == [v2["id"]]


def test_delete_version_rejects_mismatched_chapter(client: TestClient) -> None:
    _, c1 = _make_project_with_chapter(client)
    _, c2 = _make_project_with_chapter(client)

    snap = client.post(f"/api/chapters/{c1}/versions", json={"label": "x"}).json()
    r = client.delete(f"/api/chapters/{c2}/versions/{snap['id']}")
    assert r.status_code == 404
    # 原章节下还在
    items = client.get(f"/api/chapters/{c1}/versions").json()
    assert len(items) == 1


def test_delete_unknown_version_404(client: TestClient) -> None:
    _, cid = _make_project_with_chapter(client)
    r = client.delete(f"/api/chapters/{cid}/versions/99999")
    assert r.status_code == 404
