from io import BytesIO

from fastapi.testclient import TestClient


def _upload(client: TestClient, **fields):
    """构造 multipart/form-data 请求,文件作为 file 字段附加。"""
    file_bytes = fields.pop("file_bytes")
    file_name = fields.pop("file_name", "novel.txt")
    files = {"file": (file_name, BytesIO(file_bytes), "text/plain")}
    data = {k: v for k, v in fields.items() if v is not None}
    return client.post("/api/projects/import-novel", data=data, files=files)


def test_preview_chinese_novel(client: TestClient) -> None:
    text = "第一章 起\nA\nB\n第二章 承\nC\n第三章 转\nD\n第四章 合\nE"
    r = client.post(
        "/api/projects/import-novel/preview",
        files={"file": ("novel.txt", BytesIO(text.encode("utf-8")), "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["chapter_count"] == 4
    assert len(body["preview"]) == 4
    assert body["preview"][0]["title"] == "起"


def test_import_novel_creates_project_and_chapters(client: TestClient) -> None:
    text = "第一章 序\n正文一段。\n第二章 终\n正文二段。"
    r = _upload(
        client,
        name="导入的小说",
        description="测试用",
        file_bytes=text.encode("utf-8"),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["chapter_count"] == 2
    pid = body["id"]

    chapters = client.get(f"/api/projects/{pid}/chapters").json()
    assert len(chapters) == 2
    assert chapters[0]["title"] == "序"
    assert chapters[1]["order_index"] > chapters[0]["order_index"]


def test_import_novel_with_genre_and_tags(client: TestClient) -> None:
    text = "第一章 一\nA\n第二章 二\nB"
    r = _upload(
        client,
        name="末世异能",
        genre="urban",
        tags='["apocalypse","esper"]',
        progression_system="esper",
        file_bytes=text.encode("utf-8"),
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    proj = client.get(f"/api/projects/{pid}").json()
    assert proj["genre"] == "urban"
    assert proj["tags"] == ["apocalypse", "esper"]
    assert proj["progression_enabled"] is True

    ladders = client.get(f"/api/projects/{pid}/ladders").json()
    assert len(ladders) == 1
    assert ladders[0]["name"] == "异能等级"


def test_import_novel_gbk_encoding(client: TestClient) -> None:
    """老 txt 多用 GBK 编码,后端需要兜底。"""
    text = "第一章 中文\n正文内容\n第二章 编码测试\n更多正文"
    r = _upload(
        client,
        name="GBK小说",
        file_bytes=text.encode("gbk"),
    )
    assert r.status_code == 201
    assert r.json()["chapter_count"] == 2


def test_import_novel_no_chapter_marker(client: TestClient) -> None:
    """没有章节标记时整文作为单章。"""
    text = "这是一段连续的正文,没有任何章节标题。" * 20
    r = _upload(client, name="单章小说", file_bytes=text.encode("utf-8"))
    assert r.status_code == 201
    assert r.json()["chapter_count"] == 1


def test_import_novel_duplicate_name(client: TestClient) -> None:
    client.post("/api/projects", json={"name": "重名"})
    r = _upload(client, name="重名", file_bytes=b"\xe7\xac\xac\xe4\xb8\x80\xe7\xab\xa0 a")
    assert r.status_code == 400
