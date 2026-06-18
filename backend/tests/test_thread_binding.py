"""事件→主线回挂 + 状态自动推进测试。

ai_client.complete 用 monkeypatch 替成同步桩,避免真发起网络请求。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)


def _setup(client: TestClient, *, with_synopsis=True) -> tuple[int, int]:
    body = {"name": f"事件回挂-{next(_name_seq)}"}
    if with_synopsis:
        body["synopsis"] = "少年得宝物,登天阶,最终守护人间。"
    pr = client.post("/api/projects", json=body)
    pid = pr.json()["id"]
    cr = client.post(f"/api/projects/{pid}/chapters", json={"title": "首章"})
    cid = cr.json()["id"]
    client.put(f"/api/chapters/{cid}/content", json={"content": "本章正文" * 30})
    return pid, cid


def _make_thread(client: TestClient, pid: int, **fields) -> int:
    body = {"title": fields.get("title", "复仇线")}
    for k in ("description", "planned_arc", "status", "importance"):
        if k in fields:
            body[k] = fields[k]
    return client.post(f"/api/projects/{pid}/threads", json=body).json()["id"]


def _stub_complete(payload: str):
    async def _fn(*args, **kwargs):
        return payload
    return _fn


# ============ 抽取时绑定 thread_id ============


def test_extract_plot_binds_thread_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, cid = _setup(client)
    tid = _make_thread(client, pid)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            f'{{"events": [{{"title": "刺杀", "description": "山道遭袭", '
            f'"character_ids": [], "importance": 4, "thread_id": {tid}}}]}}'
        ),
    )
    r = client.post(f"/api/chapters/{cid}/auto-index")
    assert r.status_code == 200, r.text

    events = client.get(f"/api/projects/{pid}/plot/events").json()
    assert len(events) == 1
    assert events[0]["thread_id"] == tid


def test_extract_plot_drops_invalid_thread_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AI 给的 thread_id 不在白名单里(已收主线 / 别工程的线 / 瞎编),应置 null,不报错。"""
    pid, cid = _setup(client)
    _make_thread(client, pid)  # 有主线但 AI 不引用
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"events": [{"title": "X", "description": "", '
            '"character_ids": [], "importance": 3, "thread_id": 99999}]}'
        ),
    )
    r = client.post(f"/api/chapters/{cid}/auto-index")
    assert r.status_code == 200
    events = client.get(f"/api/projects/{pid}/plot/events").json()
    assert events[0]["thread_id"] is None


def test_extract_plot_thread_id_null_ok(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AI 显式给 null 表示「不属于任何线」,要正常入库。"""
    pid, cid = _setup(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"events": [{"title": "X", "description": "", '
            '"character_ids": [], "importance": 3, "thread_id": null}]}'
        ),
    )
    r = client.post(f"/api/chapters/{cid}/auto-index")
    assert r.status_code == 200
    events = client.get(f"/api/projects/{pid}/plot/events").json()
    assert events[0]["thread_id"] is None


# ============ 状态自动推进 ============


def test_planning_thread_auto_promoted_to_active(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, cid = _setup(client)
    tid = _make_thread(client, pid)  # 默认 planning
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            f'{{"events": [{{"title": "T", "description": "", '
            f'"character_ids": [], "importance": 3, "thread_id": {tid}}}]}}'
        ),
    )
    client.post(f"/api/chapters/{cid}/auto-index")

    after = client.get(f"/api/threads/{tid}").json()
    assert after["status"] == "active"


def test_active_thread_stays_active(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """已 active 的线不应被改回任何状态,继续 active。"""
    pid, cid = _setup(client)
    tid = _make_thread(client, pid, status="active")
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            f'{{"events": [{{"title": "T", "description": "", '
            f'"character_ids": [], "importance": 3, "thread_id": {tid}}}]}}'
        ),
    )
    client.post(f"/api/chapters/{cid}/auto-index")
    assert client.get(f"/api/threads/{tid}").json()["status"] == "active"


def test_resolved_thread_not_touched(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """已 resolved 的线不该被 AI 抽到(白名单已过滤),即便事件命中也不动状态。"""
    pid, cid = _setup(client)
    tid = _make_thread(client, pid, status="resolved")
    # AI 试图引用 resolved 线 → 服务层应当拒绝(thread_id 置 null)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            f'{{"events": [{{"title": "T", "description": "", '
            f'"character_ids": [], "importance": 3, "thread_id": {tid}}}]}}'
        ),
    )
    client.post(f"/api/chapters/{cid}/auto-index")
    assert client.get(f"/api/threads/{tid}").json()["status"] == "resolved"
    events = client.get(f"/api/projects/{pid}/plot/events").json()
    assert events[0]["thread_id"] is None


# ============ 跨工程隔离 ============


def test_create_event_with_cross_project_thread_id_drops_to_null(
    client: TestClient,
) -> None:
    pid_a, _ = _setup(client)
    pid_b, cid_b = _setup(client)
    tid_a = _make_thread(client, pid_a)  # A 工程的主线
    # 在 B 工程下手工建事件,引用 A 工程的 thread_id → 服务层置 null
    r = client.post(
        f"/api/projects/{pid_b}/plot/events",
        json={"chapter_id": cid_b, "title": "X", "thread_id": tid_a},
    )
    assert r.status_code == 201
    assert r.json()["thread_id"] is None


# ============ 删除主线时事件保留(SET NULL) ============


def test_delete_thread_keeps_events_with_null(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, cid = _setup(client)
    tid = _make_thread(client, pid)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            f'{{"events": [{{"title": "T", "description": "", '
            f'"character_ids": [], "importance": 3, "thread_id": {tid}}}]}}'
        ),
    )
    client.post(f"/api/chapters/{cid}/auto-index")
    assert client.get(f"/api/projects/{pid}/plot/events").json()[0]["thread_id"] == tid

    # 删主线
    assert client.delete(f"/api/threads/{tid}").status_code == 204

    # 事件还在,thread_id 变 null
    events = client.get(f"/api/projects/{pid}/plot/events").json()
    assert len(events) == 1
    assert events[0]["thread_id"] is None


# ============ 主线相关事件接口 ============


def test_list_events_for_thread(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, cid = _setup(client)
    tid = _make_thread(client, pid)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            f'{{"events": ['
            f'{{"title": "事件A", "description": "", "character_ids": [], "importance": 3, "thread_id": {tid}}},'
            f'{{"title": "事件B", "description": "", "character_ids": [], "importance": 4, "thread_id": null}}'
            f']}}'
        ),
    )
    client.post(f"/api/chapters/{cid}/auto-index")

    r = client.get(f"/api/threads/{tid}/events")
    assert r.status_code == 200
    data = r.json()
    # 只有挂在这条线上的那一条
    assert [e["title"] for e in data] == ["事件A"]
    assert data[0]["chapter_id"] == cid
    assert data[0]["chapter_order_index"] == 1


def test_list_events_for_unknown_thread_404(client: TestClient) -> None:
    r = client.get("/api/threads/99999/events")
    assert r.status_code == 404
