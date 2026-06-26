"""翻译一致性检查(M4)测试。

只测纯字符串匹配的核心语义,不模拟 AI(M4 不用 AI)。
"""

from itertools import count

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.chapter_version import ChapterVersion

_name_seq = count(1)


def _make_project_with_chapter(
    client: TestClient, content: str = "李慕白下山。"
) -> tuple[int, int]:
    pid = client.post(
        "/api/projects", json={"name": f"一致性-{next(_name_seq)}"}
    ).json()["id"]
    cid = client.post(
        f"/api/projects/{pid}/chapters", json={"title": "首章"}
    ).json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": content})
    return pid, cid


def _seed_translated_version(
    db: Session, chapter_id: int, content: str, lang: str = "en-US"
) -> int:
    v = ChapterVersion(
        chapter_id=chapter_id,
        content=content,
        word_count=len(content.split()),
        reason="translated",
        label=f"AI 翻译 → {lang}",
        lang=lang,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v.id


def test_consistency_flags_missing_target(
    client: TestClient, db_session: Session
) -> None:
    pid, cid = _make_project_with_chapter(client, "李慕白下山,与张飞相遇。")
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
    # 译文只有 Li Mubai,丢了 Zhang Fei
    _seed_translated_version(
        db_session, cid, "Li Mubai descended and met someone."
    )

    r = client.get(
        f"/api/projects/{pid}/translation-consistency?target_lang=en-US"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["checked_chapters"] == 1
    assert body["glossary_size"] == 2
    issues = body["issues"]
    assert len(issues) == 1
    assert issues[0]["source"] == "张飞"
    assert issues[0]["expected_target"] == "Zhang Fei"


def test_consistency_skips_terms_not_in_original(
    client: TestClient, db_session: Session
) -> None:
    """术语在中文原文里没出现 → 不算 issue(漏译只能定位到出现过的)"""
    pid, cid = _make_project_with_chapter(client, "李慕白下山。")
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "玉娇龙",
            "target": "Jen",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )
    _seed_translated_version(db_session, cid, "Li Mubai descended.")
    r = client.get(
        f"/api/projects/{pid}/translation-consistency?target_lang=en-US"
    )
    body = r.json()
    assert body["issues"] == []


def test_consistency_skips_empty_target(
    client: TestClient, db_session: Session
) -> None:
    pid, cid = _make_project_with_chapter(client, "李慕白下山。")
    # target 为空的条目不参与一致性比对(无约束可言)
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "李慕白",
            "target": "",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )
    _seed_translated_version(db_session, cid, "Mubai went down.")
    r = client.get(
        f"/api/projects/{pid}/translation-consistency?target_lang=en-US"
    )
    body = r.json()
    assert body["glossary_size"] == 0
    assert body["issues"] == []


def test_consistency_uses_latest_version_per_chapter(
    client: TestClient, db_session: Session
) -> None:
    """同章多个翻译版本,只用最新一个判断"""
    pid, cid = _make_project_with_chapter(client, "李慕白下山。")
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "李慕白",
            "target": "Li Mubai",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )
    # 老版本译错了
    _seed_translated_version(db_session, cid, "Mubai descended.")
    # 新版本译对了
    _seed_translated_version(db_session, cid, "Li Mubai descended.")
    r = client.get(
        f"/api/projects/{pid}/translation-consistency?target_lang=en-US"
    )
    body = r.json()
    assert body["issues"] == []


def test_consistency_chapter_without_translation_skipped(
    client: TestClient, db_session: Session
) -> None:
    """章节还没翻译过 → checked_chapters 不计,不挂 issue"""
    pid, cid = _make_project_with_chapter(client, "李慕白下山。")
    client.post(
        f"/api/projects/{pid}/glossary",
        json={
            "source": "李慕白",
            "target": "Li Mubai",
            "target_lang": "en-US",
            "entry_type": "person",
        },
    )
    # 不 seed 任何 version
    r = client.get(
        f"/api/projects/{pid}/translation-consistency?target_lang=en-US"
    )
    body = r.json()
    assert body["total_chapters"] == 1
    assert body["checked_chapters"] == 0
    assert body["issues"] == []


def test_consistency_unknown_project_404(client: TestClient) -> None:
    r = client.get(
        "/api/projects/99999/translation-consistency?target_lang=en-US"
    )
    assert r.status_code == 404
