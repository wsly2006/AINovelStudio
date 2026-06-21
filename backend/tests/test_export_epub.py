"""EPUB 导出验证。"""

import zipfile
from io import BytesIO

from fastapi.testclient import TestClient


def _seed_project_with_meta(client: TestClient) -> int:
    pid = client.post(
        "/api/projects",
        json={
            "name": "EPUB 测试",
            "description": "短简介",
            "genre": "xianxia",
            "pen_name": "Alex Wang",
            "series_name": "Sword & Spell",
            "series_index": 2,
            "blurb": "A young cultivator rises against destiny.",
            "keywords": ["cultivation", "rebirth"],
            "categories": ["Fantasy", "Action"],
        },
    ).json()["id"]
    c1 = client.post(f"/api/projects/{pid}/chapters", json={"title": "初入山门"}).json()["id"]
    c2 = client.post(f"/api/projects/{pid}/chapters", json={"title": "拜师"}).json()["id"]
    client.put(
        f"/api/chapters/{c1}/content",
        json={"content": "山门之外，云雾缭绕。\n\n少年抬眼，看见了那块石碑。"},
    )
    client.put(
        f"/api/chapters/{c2}/content",
        json={"content": "老者抚须道：「孺子可教。」"},
    )
    return pid


def test_export_epub_returns_valid_zip(client: TestClient):
    pid = _seed_project_with_meta(client)
    r = client.get(f"/api/projects/{pid}/export.epub")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/epub+zip"
    assert "attachment" in r.headers.get("content-disposition", "")

    # EPUB 本质是 zip,验证可被解压且包含必备文件
    body = r.content
    assert len(body) > 1000  # 至少不空
    assert body[:2] == b"PK"  # zip magic

    with zipfile.ZipFile(BytesIO(body)) as zf:
        names = zf.namelist()
        # mimetype 必须存在且是首文件
        assert "mimetype" in names
        assert zf.read("mimetype") == b"application/epub+zip"
        # 至少一个 OPF / NAV
        assert any(n.endswith(".opf") for n in names), names
        # 章节文件
        chap_files = [n for n in names if n.startswith("chap_") or "chap_" in n]
        assert len(chap_files) >= 2

        # OPF 中应含 blurb / keywords / pen_name
        opf_name = next(n for n in names if n.endswith(".opf"))
        opf = zf.read(opf_name).decode("utf-8")
        assert "Alex Wang" in opf
        assert "A young cultivator" in opf
        assert "cultivation" in opf
        assert "calibre:series" in opf  # 系列元数据


def test_export_epub_404_for_missing_project(client: TestClient):
    r = client.get("/api/projects/999999/export.epub")
    assert r.status_code == 404
