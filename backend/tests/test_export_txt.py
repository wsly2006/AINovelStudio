"""txt 导出验证。"""

import zipfile
from io import BytesIO

from fastapi.testclient import TestClient


def _seed(client: TestClient) -> int:
    pid = client.post(
        "/api/projects",
        json={
            "name": "txt 导出测试",
            "blurb": "短简介",
            "pen_name": "墨白",
        },
    ).json()["id"]
    c1 = client.post(f"/api/projects/{pid}/chapters", json={"title": "初临"}).json()["id"]
    c2 = client.post(f"/api/projects/{pid}/chapters", json={"title": "试剑"}).json()["id"]
    client.put(f"/api/chapters/{c1}/content", json={"content": "晨雾未散。\n\n少年握紧了剑柄。"})
    client.put(f"/api/chapters/{c2}/content", json={"content": "剑光乍现，余响绕梁。"})
    return pid


def test_export_txt_whole_utf8(client: TestClient):
    pid = _seed(client)
    r = client.get(f"/api/projects/{pid}/export.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    body = r.content.decode("utf-8")
    assert "第 1 章 初临" in body
    assert "第 2 章 试剑" in body
    assert "墨白" in body
    assert "晨雾未散" in body


def test_export_txt_whole_gb18030(client: TestClient):
    pid = _seed(client)
    r = client.get(f"/api/projects/{pid}/export.txt?encoding=gb18030")
    assert r.status_code == 200
    body = r.content.decode("gb18030")
    assert "第 1 章" in body
    assert "晨雾未散" in body


def test_export_txt_chapters_zip(client: TestClient):
    pid = _seed(client)
    r = client.get(f"/api/projects/{pid}/export.txt?mode=chapters")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(r.content)) as zf:
        names = zf.namelist()
        assert len(names) == 2
        # 文件名按 order_index 编号 + 标题
        assert any(n.startswith("0001_") for n in names)
        assert any(n.startswith("0002_") for n in names)
        # 章节内容存在
        first = next(n for n in names if n.startswith("0001_"))
        text = zf.read(first).decode("utf-8")
        assert "第 1 章 初临" in text
        assert "晨雾未散" in text


def test_export_txt_invalid_encoding(client: TestClient):
    pid = _seed(client)
    r = client.get(f"/api/projects/{pid}/export.txt?encoding=latin-1")
    assert r.status_code == 400


def test_export_txt_invalid_mode(client: TestClient):
    pid = _seed(client)
    r = client.get(f"/api/projects/{pid}/export.txt?mode=foo")
    assert r.status_code == 400
