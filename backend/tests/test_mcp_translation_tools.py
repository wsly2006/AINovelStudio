"""MCP 翻译工具(P0-M6)测试。

直接调 translation.py 暴露的函数 —— 注册表里的 Tool.call() 会走 pre-hook,
本组测试关注业务逻辑,所以绕过 hooks 直接调函数本身(hooks 在
test_mcp_tools.py 里另有覆盖)。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai import client as ai_client_module
from app.ai.tools import translation as t
from app.models.chapter_version import ChapterVersion

_name_seq = count(1)


def _seed_project_with_chapter(
    client: TestClient, content: str = "李慕白下山,与张飞相遇。"
) -> tuple[int, int]:
    pid = client.post(
        "/api/projects", json={"name": f"mcp翻译-{next(_name_seq)}"}
    ).json()["id"]
    cid = client.post(
        f"/api/projects/{pid}/chapters", json={"title": "首章"}
    ).json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": content})
    return pid, cid


def _stub_stream(deltas: list[str]):
    async def _fn(*args, **kwargs):
        for d in deltas:
            yield d

    return _fn


def test_list_glossary_returns_entries(client: TestClient) -> None:
    pid, _ = _seed_project_with_chapter(client)
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "李慕白",
            "target": "Li Mubai",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "张飞",
            "target": "Zhang Fei",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )

    rows = t.list_glossary(project_id=pid, target_lang="en-US")
    assert isinstance(rows, list)
    assert {r["source"] for r in rows} == {"李慕白", "张飞"}
    assert all(r["target_lang"] == "en-US" for r in rows)


def test_upsert_glossary_creates_then_updates(client: TestClient) -> None:
    pid, _ = _seed_project_with_chapter(client)

    r1 = t.upsert_glossary_entry(
        project_id=pid,
        source="李慕白",
        target="Li Muba",  # 第一次译错
        entry_type="person",
    )
    assert r1["action"] == "created"
    entry_id = r1["entry"]["id"]

    r2 = t.upsert_glossary_entry(
        project_id=pid,
        source="李慕白",
        target="Li Mubai",  # 修正
        entry_type="person",
        notes="武当宗师",
    )
    assert r2["action"] == "updated"
    assert r2["entry"]["id"] == entry_id
    assert r2["entry"]["target"] == "Li Mubai"
    assert r2["entry"]["notes"] == "武当宗师"


def test_upsert_glossary_respects_locked(client: TestClient) -> None:
    pid, _ = _seed_project_with_chapter(client)
    created = client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "李慕白",
            "target": "Li Mubai",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    ).json()
    # 锁定
    client.patch(f"/api/glossary/{created['id']}", json={"locked": True})

    r = t.upsert_glossary_entry(
        project_id=pid,
        source="李慕白",
        target="Master Li",
        entry_type="person",
    )
    assert r["action"] == "skipped_locked"
    # 译文没动
    after = client.get(f"/api/glossary/{created['id']}").json()
    assert after["target"] == "Li Mubai"


def test_translate_chapter_runs_and_returns_preview(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, cid = _seed_project_with_chapter(client, "李慕白下山。")
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "李慕白",
            "target": "Li Mubai",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )
    monkeypatch.setattr(
        ai_client_module,
        "stream_chat",
        _stub_stream(["Li Mubai ", "descended ", "the mountain."]),
    )

    result = t.translate_chapter(chapter_id=cid, target_lang="en-US")

    assert result["chapter_id"] == cid
    assert result["target_lang"] == "en-US"
    assert isinstance(result["version_id"], int)
    assert "Li Mubai" in result["content_preview"]
    assert result["truncated"] is False
    # 落库一条 en-US 版本
    versions = client.get(
        f"/api/chapters/{cid}/versions?lang=en-US"
    ).json()
    assert len(versions) == 1
    assert versions[0]["reason"] == "translated"


def test_translate_chapter_preview_truncates(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """译文超过 500 字符时 preview 应当被截断且 truncated=True"""
    pid, cid = _seed_project_with_chapter(client, "本章正文。")
    long_text = "A " * 400  # 800 字符
    monkeypatch.setattr(
        ai_client_module, "stream_chat", _stub_stream([long_text])
    )
    result = t.translate_chapter(chapter_id=cid, target_lang="en-US")
    assert result["truncated"] is True
    assert len(result["content_preview"]) <= 501  # 500 + 省略号


def test_check_translation_consistency_returns_report(
    client: TestClient, db_session: Session
) -> None:
    pid, cid = _seed_project_with_chapter(client, "李慕白下山,张飞相迎。")
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "李慕白",
            "target": "Li Mubai",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "张飞",
            "target": "Zhang Fei",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )
    # 译文里只有 Li Mubai —— 漏了 Zhang Fei
    v = ChapterVersion(
        chapter_id=cid,
        content="Li Mubai descended and met someone.",
        word_count=6,
        reason="translated",
        label="seed",
        lang="en-US",
    )
    db_session.add(v)
    db_session.commit()

    report = t.check_translation_consistency(
        project_id=pid, target_lang="en-US"
    )
    assert report["checked_chapters"] == 1
    assert report["glossary_size"] == 2
    sources = [it["source"] for it in report["issues"]]
    assert "张飞" in sources
    assert "李慕白" not in sources


def test_get_chapter_version_returns_full_content(
    client: TestClient, db_session: Session
) -> None:
    pid, cid = _seed_project_with_chapter(client, "原文。")
    v = ChapterVersion(
        chapter_id=cid,
        content="Full English content here.",
        word_count=4,
        reason="translated",
        label="manual",
        lang="en-US",
    )
    db_session.add(v)
    db_session.commit()
    db_session.refresh(v)

    detail = t.get_chapter_version(version_id=v.id)
    assert detail["id"] == v.id
    assert detail["content"] == "Full English content here."
    assert detail["lang"] == "en-US"


def test_translation_tools_registered() -> None:
    """烟测:5 个工具都进了 REGISTRY"""
    from app.ai.tools.registry import REGISTRY

    expected = {
        "list_glossary",
        "upsert_glossary_entry",
        "translate_chapter",
        "check_translation_consistency",
        "get_chapter_version",
    }
    assert expected.issubset(REGISTRY.keys())
    # dangerous 标记正确
    assert REGISTRY["upsert_glossary_entry"].dangerous is True
    assert REGISTRY["translate_chapter"].dangerous is True
    assert REGISTRY["list_glossary"].dangerous is False
