from fastapi.testclient import TestClient


def _create_project(client: TestClient, name: str = "工程A") -> int:
    return client.post("/api/projects", json={"name": name}).json()["id"]


def test_list_chapters_empty(client: TestClient) -> None:
    pid = _create_project(client)
    r = client.get(f"/api/projects/{pid}/chapters")
    assert r.status_code == 200
    assert r.json() == []


def test_list_chapters_project_not_found(client: TestClient) -> None:
    r = client.get("/api/projects/9999/chapters")
    assert r.status_code == 404


def test_create_chapter_assigns_order(client: TestClient) -> None:
    pid = _create_project(client)
    r1 = client.post(f"/api/projects/{pid}/chapters", json={"title": "第一章"})
    assert r1.status_code == 201
    assert r1.json()["order_index"] == 1
    assert r1.json()["status"] == "draft"
    assert r1.json()["word_count"] == 0
    assert r1.json()["content"] == ""

    r2 = client.post(f"/api/projects/{pid}/chapters", json={"title": "第二章"})
    assert r2.json()["order_index"] == 2

    r3 = client.post(f"/api/projects/{pid}/chapters", json={"title": "第三章"})
    assert r3.json()["order_index"] == 3


def test_create_chapter_empty_title_allowed(client: TestClient) -> None:
    """空 title 现在表示「只用『第 N 章』前缀,无副标题」,前后端约定允许。"""
    pid = _create_project(client)
    r = client.post(f"/api/projects/{pid}/chapters", json={"title": "  "})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == ""
    assert body["order_index"] == 1


def test_create_chapter_with_summary(client: TestClient) -> None:
    pid = _create_project(client)
    r = client.post(
        f"/api/projects/{pid}/chapters",
        json={"title": "初遇", "summary": "主角下山"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "初遇"
    assert body["summary"] == "主角下山"


def test_get_chapter_detail(client: TestClient) -> None:
    pid = _create_project(client)
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "X"}).json()["id"]
    r = client.get(f"/api/chapters/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "X"
    assert "content" in body


def test_update_chapter(client: TestClient) -> None:
    pid = _create_project(client)
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "旧名"}).json()["id"]
    r = client.patch(
        f"/api/chapters/{cid}",
        json={"title": "新名", "summary": "梗概", "status": "writing"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "新名"
    assert body["summary"] == "梗概"
    assert body["status"] == "writing"


def test_delete_chapter(client: TestClient) -> None:
    pid = _create_project(client)
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "待删"}).json()["id"]
    r = client.delete(f"/api/chapters/{cid}")
    assert r.status_code == 204

    r = client.get(f"/api/chapters/{cid}")
    assert r.status_code == 404


def test_reorder_chapters(client: TestClient) -> None:
    pid = _create_project(client)
    ids = [
        client.post(f"/api/projects/{pid}/chapters", json={"title": f"第{i}章"}).json()["id"]
        for i in range(1, 4)
    ]
    # 反转顺序
    r = client.post(
        f"/api/projects/{pid}/chapters/reorder",
        json={"chapter_ids": list(reversed(ids))},
    )
    assert r.status_code == 200
    items = r.json()
    assert [c["id"] for c in items] == list(reversed(ids))
    assert [c["order_index"] for c in items] == [1, 2, 3]


def test_reorder_mismatch(client: TestClient) -> None:
    pid = _create_project(client)
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "X"}).json()["id"]
    r = client.post(
        f"/api/projects/{pid}/chapters/reorder",
        json={"chapter_ids": [cid, 9999]},
    )
    assert r.status_code == 400


def test_cascade_delete_on_project_delete(client: TestClient) -> None:
    pid = _create_project(client)
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "C"}).json()["id"]

    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204

    r = client.get(f"/api/chapters/{cid}")
    assert r.status_code == 404


def test_project_derived_fields_reflect_chapters(client: TestClient) -> None:
    pid = _create_project(client)
    # 派生字段:章节数 / 字数 / 最后编辑时间
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "C1"}).json()["id"]
    # 通过 patch 把 status 变更让 updated_at 刷新(content 路径在 Phase 3)
    client.patch(f"/api/chapters/{cid}", json={"status": "writing"})

    r = client.get("/api/projects")
    items = r.json()
    target = next(p for p in items if p["id"] == pid)
    assert target["chapter_count"] == 1
    assert target["word_count"] == 0  # 暂无 content 接口


def test_save_content_updates_word_count(client: TestClient) -> None:
    pid = _create_project(client)
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "C"}).json()["id"]

    r = client.put(f"/api/chapters/{cid}/content", json={"content": "你好,世界! Hello world."})
    assert r.status_code == 200
    body = r.json()
    # 去除空白后的字符数:中英文混合,空白计 0
    assert body["word_count"] > 0

    # 详情应包含正文
    detail = client.get(f"/api/chapters/{cid}").json()
    assert detail["content"].startswith("你好")

    # project.word_count 派生字段反映新值
    proj = next(p for p in client.get("/api/projects").json() if p["id"] == pid)
    assert proj["word_count"] == body["word_count"]


def test_save_content_chapter_not_found(client: TestClient) -> None:
    r = client.put("/api/chapters/9999/content", json={"content": "x"})
    assert r.status_code == 404
