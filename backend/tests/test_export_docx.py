"""docx 导出验证。"""

import zipfile
from io import BytesIO

from fastapi.testclient import TestClient


def _seed(client: TestClient) -> int:
    pid = client.post(
        "/api/projects",
        json={
            "name": "docx 导出测试",
            "pen_name": "Alex",
            "blurb": "A test description.",
            "keywords": ["adventure", "fantasy"],
            "categories": ["Fiction"],
        },
    ).json()["id"]
    c1 = client.post(f"/api/projects/{pid}/chapters", json={"title": "起"}).json()["id"]
    c2 = client.post(f"/api/projects/{pid}/chapters", json={"title": "承"}).json()["id"]
    client.put(f"/api/chapters/{c1}/content", json={"content": "段一开头。\n\n段二开头。"})
    client.put(f"/api/chapters/{c2}/content", json={"content": "再来一段。"})
    return pid


def test_export_docx_returns_valid_package(client: TestClient):
    pid = _seed(client)
    r = client.get(f"/api/projects/{pid}/export.docx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    body = r.content
    assert body[:2] == b"PK"  # docx 是 zip 包

    # docx 内 word/document.xml 应包含章节标题和正文
    with zipfile.ZipFile(BytesIO(body)) as zf:
        names = zf.namelist()
        assert "word/document.xml" in names
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "第 1 章 起" in doc_xml
        assert "第 2 章 承" in doc_xml
        assert "段一开头" in doc_xml
        # core 属性
        assert "docProps/core.xml" in names
        core = zf.read("docProps/core.xml").decode("utf-8")
        assert "Alex" in core
        assert "A test description" in core


def test_export_docx_404(client: TestClient):
    r = client.get("/api/projects/9999/export.docx")
    assert r.status_code == 404
