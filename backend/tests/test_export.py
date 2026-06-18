from fastapi.testclient import TestClient


def _seed(client: TestClient) -> dict:
    """造一份完整的工程数据,返回 ids。"""
    pid = client.post(
        "/api/projects",
        json={"name": "导出测试", "description": "用于导出/导入测试", "genre": "玄幻"},
    ).json()["id"]
    c1 = client.post(f"/api/projects/{pid}/chapters", json={"title": "第一章"}).json()["id"]
    c2 = client.post(f"/api/projects/{pid}/chapters", json={"title": "第二章"}).json()["id"]
    client.put(f"/api/chapters/{c1}/content", json={"content": "正文一"})
    client.put(f"/api/chapters/{c2}/content", json={"content": "正文二"})

    h1 = client.post(
        f"/api/projects/{pid}/characters",
        json={"name": "甲", "aliases": ["小甲"], "role": "主角", "profile": "少年"},
    ).json()["id"]
    h2 = client.post(f"/api/projects/{pid}/characters", json={"name": "乙"}).json()["id"]

    client.post(
        f"/api/projects/{pid}/relations",
        json={"from_id": h1, "to_id": h2, "type": "朋友", "description": "总角之交"},
    )
    client.post(
        f"/api/projects/{pid}/plot/events",
        json={
            "chapter_id": c1,
            "title": "相遇",
            "description": "甲乙首次相遇",
            "character_ids": [h1, h2],
            "importance": 4,
            "order_in_chapter": 1,
        },
    )
    return {"pid": pid, "c1": c1, "c2": c2, "h1": h1, "h2": h2}


def test_export_json(client: TestClient) -> None:
    ids = _seed(client)
    r = client.get(f"/api/projects/{ids['pid']}/export.json")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")

    data = r.json()
    assert data["format"] == "ai_novel_writer.export"
    assert data["project"]["name"] == "导出测试"
    assert len(data["chapters"]) == 2
    assert len(data["characters"]) == 2
    assert len(data["relations"]) == 1
    assert len(data["plot_events"]) == 1
    # 章节正文要保留
    assert data["chapters"][0]["content"] == "正文一"


def test_export_markdown(client: TestClient) -> None:
    ids = _seed(client)
    r = client.get(f"/api/projects/{ids['pid']}/export.md")
    assert r.status_code == 200
    text = r.text
    assert "# 导出测试" in text
    assert "## 第 1 章" in text
    assert "正文一" in text
    assert "正文二" in text


def test_export_not_found(client: TestClient) -> None:
    assert client.get("/api/projects/9999/export.json").status_code == 404
    assert client.get("/api/projects/9999/export.md").status_code == 404


def test_import_roundtrip(client: TestClient) -> None:
    ids = _seed(client)
    exported = client.get(f"/api/projects/{ids['pid']}/export.json").json()

    files = {"file": ("export.json", __import__("json").dumps(exported).encode("utf-8"), "application/json")}
    r = client.post("/api/projects/import", files=files)
    assert r.status_code == 201
    body = r.json()
    assert body["chapter_count"] == 2
    assert body["character_count"] == 2
    new_pid = body["id"]
    assert new_pid != ids["pid"]
    assert "导出测试" in body["name"]  # 重名自动加后缀

    # 数据重映射:章节 / 人物 / 关系 / 事件都还在,id 不一样
    chapters = client.get(f"/api/projects/{new_pid}/chapters").json()
    assert [c["title"] for c in chapters] == ["第一章", "第二章"]

    new_c1 = chapters[0]
    detail = client.get(f"/api/chapters/{new_c1['id']}").json()
    assert detail["content"] == "正文一"
    assert new_c1["word_count"] > 0  # 字数重算

    new_chars = client.get(f"/api/projects/{new_pid}/characters").json()
    assert {c["name"] for c in new_chars} == {"甲", "乙"}

    new_rels = client.get(f"/api/projects/{new_pid}/relations").json()
    assert len(new_rels) == 1

    new_events = client.get(f"/api/projects/{new_pid}/plot/events").json()
    assert len(new_events) == 1
    # 涉及人物 id 应该是新工程的 id
    new_char_ids = {c["id"] for c in new_chars}
    assert all(cid in new_char_ids for cid in new_events[0]["character_ids"])


def test_import_invalid_format(client: TestClient) -> None:
    files = {"file": ("bad.json", b'{"foo": "bar"}', "application/json")}
    r = client.post("/api/projects/import", files=files)
    assert r.status_code == 400


def test_import_bad_json(client: TestClient) -> None:
    files = {"file": ("bad.json", b"not json", "application/json")}
    r = client.post("/api/projects/import", files=files)
    assert r.status_code == 400
