"""节拍-事件对账测试。

ai_client.complete 用 monkeypatch 替成同步桩,避免真发起网络请求。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)


def _setup_chapter_with_beats(client: TestClient) -> int:
    pr = client.post("/api/projects", json={"name": f"对账-{next(_name_seq)}"})
    pid = pr.json()["id"]
    cr = client.post(f"/api/projects/{pid}/chapters", json={"title": "首章"})
    cid = cr.json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": "正文" * 30})
    client.patch(
        f"/api/chapters/{cid}",
        json={
            "beats": [
                {"title": "拍 A", "detail": "AAA"},
                {"title": "拍 B", "detail": "BBB"},
                {"title": "拍 C", "detail": "CCC"},
            ]
        },
    )
    return cid


def _stub_complete(payload: str):
    async def _fn(*args, **kwargs):
        return payload
    return _fn


# ============ 没节拍 / 没事件 的退化路径 ============


def test_align_without_beats_returns_zero(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pr = client.post("/api/projects", json={"name": f"无节拍-{next(_name_seq)}"})
    pid = pr.json()["id"]
    cid = client.post(f"/api/projects/{pid}/chapters", json={"title": "X"}).json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": "X"})

    # 没节拍,根本不该调 AI
    async def _fail(*a, **kw):
        raise AssertionError("AI should not be called when no beats")

    monkeypatch.setattr(ai_client_module, "complete", _fail)
    r = client.post(f"/api/chapters/{cid}/ai/check-beats")
    assert r.status_code == 200
    assert r.json() == {"items": [], "covered": 0, "partial": 0, "missing": 0}


def test_align_without_events_marks_all_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """有节拍但章节里没事件 → 全 missing,不调 AI。"""
    cid = _setup_chapter_with_beats(client)

    async def _fail(*a, **kw):
        raise AssertionError("AI should not be called when no events")

    monkeypatch.setattr(ai_client_module, "complete", _fail)
    r = client.post(f"/api/chapters/{cid}/ai/check-beats")
    assert r.status_code == 200
    data = r.json()
    assert data["missing"] == 3
    assert data["covered"] == 0
    assert all(it["status"] == "missing" for it in data["items"])


# ============ 正常对账路径 ============


def test_align_persists_and_counts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _setup_chapter_with_beats(client)
    pid = client.get(f"/api/chapters/{cid}").json()["project_id"]

    # 先抽几个事件
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"events": ['
            '{"title": "事件 A", "description": "兑现拍 A", "character_ids": [], "importance": 3},'
            '{"title": "事件 B", "description": "勉强对应拍 B", "character_ids": [], "importance": 3}'
            ']}'
        ),
    )
    client.post(f"/api/chapters/{cid}/auto-index")
    events = client.get(f"/api/projects/{pid}/plot/events").json()
    eid_a, eid_b = events[0]["id"], events[1]["id"]

    # AI 给 A=covered / B=partial / C=missing
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            f'{{"items": ['
            f'{{"beat_index": 0, "status": "covered", "matched_event_ids": [{eid_a}], "note": "完美兑现"}},'
            f'{{"beat_index": 1, "status": "partial", "matched_event_ids": [{eid_b}], "note": "弱化"}},'
            f'{{"beat_index": 2, "status": "missing", "matched_event_ids": [], "note": "完全没写"}}'
            f']}}'
        ),
    )
    r = client.post(f"/api/chapters/{cid}/ai/check-beats")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data == {
        "items": [
            {"beat_index": 0, "status": "covered", "matched_event_ids": [eid_a], "note": "完美兑现"},
            {"beat_index": 1, "status": "partial", "matched_event_ids": [eid_b], "note": "弱化"},
            {"beat_index": 2, "status": "missing", "matched_event_ids": [], "note": "完全没写"},
        ],
        "covered": 1,
        "partial": 1,
        "missing": 1,
    }

    # 再 GET 章节详情,beats_alignment 应当被持久化了
    detail = client.get(f"/api/chapters/{cid}").json()
    assert detail["beats_alignment"] is not None
    assert len(detail["beats_alignment"]) == 3


def test_align_filters_invalid_event_ids(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AI 给了不属于本章的 event_id 应被过滤掉。"""
    cid = _setup_chapter_with_beats(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"events": [{"title": "X", "description": "", "character_ids": [], "importance": 3}]}'
        ),
    )
    client.post(f"/api/chapters/{cid}/auto-index")

    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"items": ['
            '{"beat_index": 0, "status": "covered", "matched_event_ids": [99999, 99998], "note": "x"},'
            '{"beat_index": 1, "status": "missing", "matched_event_ids": [], "note": "x"},'
            '{"beat_index": 2, "status": "missing", "matched_event_ids": [], "note": "x"}'
            ']}'
        ),
    )
    data = client.post(f"/api/chapters/{cid}/ai/check-beats").json()
    # 99999 / 99998 都不存在 → 全部过滤,留空数组
    assert data["items"][0]["matched_event_ids"] == []


def test_align_fills_missing_when_ai_skips_a_beat(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AI 漏判了第 2 拍 → 应自动补成 missing,不能少给一拍。"""
    cid = _setup_chapter_with_beats(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"events": [{"title": "X", "description": "", "character_ids": [], "importance": 3}]}'
        ),
    )
    client.post(f"/api/chapters/{cid}/auto-index")

    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"items": ['
            '{"beat_index": 0, "status": "covered", "matched_event_ids": [], "note": "ok"},'
            '{"beat_index": 2, "status": "missing", "matched_event_ids": [], "note": "ok"}'
            ']}'
        ),
    )
    data = client.post(f"/api/chapters/{cid}/ai/check-beats").json()
    assert len(data["items"]) == 3
    assert data["items"][1]["status"] == "missing"
    assert data["items"][1]["beat_index"] == 1


def test_align_handles_markdown_wrapped_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _setup_chapter_with_beats(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"events": [{"title": "X", "description": "", "character_ids": [], "importance": 3}]}'
        ),
    )
    client.post(f"/api/chapters/{cid}/auto-index")

    raw = '```json\n{"items": [' + ",".join(
        f'{{"beat_index": {i}, "status": "covered", "matched_event_ids": [], "note": "ok"}}'
        for i in range(3)
    ) + ']}\n```'
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(raw))
    r = client.post(f"/api/chapters/{cid}/ai/check-beats")
    assert r.status_code == 200
    assert r.json()["covered"] == 3


# ============ 节拍变化清空对账 ============


def test_changing_beats_clears_alignment(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cid = _setup_chapter_with_beats(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"events": [{"title": "X", "description": "", "character_ids": [], "importance": 3}]}'
        ),
    )
    client.post(f"/api/chapters/{cid}/auto-index")

    # 先跑一次对账,beats_alignment 应该非空
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"items": [' + ",".join(
                f'{{"beat_index": {i}, "status": "covered", "matched_event_ids": [], "note": "ok"}}'
                for i in range(3)
            ) + ']}'
        ),
    )
    client.post(f"/api/chapters/{cid}/ai/check-beats")
    assert client.get(f"/api/chapters/{cid}").json()["beats_alignment"] is not None

    # 改节拍 → beats_alignment 应被自动清空
    client.patch(
        f"/api/chapters/{cid}",
        json={"beats": [{"title": "改了", "detail": ""}]},
    )
    assert client.get(f"/api/chapters/{cid}").json()["beats_alignment"] is None


def test_align_unknown_chapter_404(client: TestClient) -> None:
    r = client.post("/api/chapters/99999/ai/check-beats")
    assert r.status_code == 404
