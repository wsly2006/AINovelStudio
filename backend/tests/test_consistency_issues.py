"""一致性问题持久化测试。

ai_client.complete 用 monkeypatch 替成同步桩,避免真发起网络请求。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)


def _make_project(client: TestClient) -> int:
    return client.post("/api/projects", json={"name": f"一致性-{next(_name_seq)}"}).json()["id"]


def _stub_complete(payload: str):
    async def _fn(*args, **kwargs):
        return payload
    return _fn


# ============ 跑扫描 + 落库 ============


def test_check_persists_issues(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"issues": ['
            '{"kind": "矛盾", "title": "人物前后描写矛盾", "detail": "X", '
            ' "related_event_ids": [1, 2], "related_character_ids": [3]},'
            '{"kind": "伏笔未收", "title": "刺客身份没解释", "detail": "Y", '
            ' "related_event_ids": [], "related_character_ids": []}'
            ']}'
        ),
    )
    r = client.post(f"/api/projects/{pid}/plot/check")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["issues"]) == 2
    assert data["open_count"] == 2
    assert data["run_id"]  # UUID

    # 全部入库,GET 能查到
    listed = client.get(f"/api/projects/{pid}/issues").json()
    assert len(listed) == 2
    assert {i["title"] for i in listed} == {"人物前后描写矛盾", "刺客身份没解释"}
    assert all(i["status"] == "open" for i in listed)


def test_check_appends_new_issues_keeping_old(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """两次扫描的 issue 应共存,不去重(每次独立 run_id)。"""
    pid = _make_project(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete('{"issues": [{"kind": "X", "title": "第一批", "detail": ""}]}'),
    )
    r1 = client.post(f"/api/projects/{pid}/plot/check").json()
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete('{"issues": [{"kind": "Y", "title": "第二批", "detail": ""}]}'),
    )
    r2 = client.post(f"/api/projects/{pid}/plot/check").json()

    assert r1["run_id"] != r2["run_id"]
    assert r2["open_count"] == 2

    titles = [i["title"] for i in client.get(f"/api/projects/{pid}/issues").json()]
    assert set(titles) == {"第一批", "第二批"}


def test_check_drops_blank_title_items(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"issues": ['
            '{"kind": "X", "title": "", "detail": "应被丢弃"},'
            '{"kind": "Y", "title": "保留", "detail": ""}'
            ']}'
        ),
    )
    r = client.post(f"/api/projects/{pid}/plot/check").json()
    assert len(r["issues"]) == 1
    assert r["issues"][0]["title"] == "保留"


def test_check_handles_markdown_wrapped_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    raw = '好的:\n```json\n{"issues": [{"kind": "X", "title": "T", "detail": ""}]}\n```'
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(raw))
    r = client.post(f"/api/projects/{pid}/plot/check").json()
    assert len(r["issues"]) == 1


def test_check_unparseable_yields_empty_no_crash(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """模型胡言乱语时,issues 给空数组,run_id 仍正常返回——别让一次坏扫描挂掉接口。"""
    pid = _make_project(client)
    monkeypatch.setattr(
        ai_client_module, "complete", _stub_complete("这根本不是 JSON")
    )
    r = client.post(f"/api/projects/{pid}/plot/check")
    assert r.status_code == 200
    assert r.json()["issues"] == []
    assert r.json()["open_count"] == 0


def test_check_unknown_project_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # complete 不应被调用
    async def _fail(*a, **kw):
        raise AssertionError("AI should not be called")

    monkeypatch.setattr(ai_client_module, "complete", _fail)
    r = client.post("/api/projects/99999/plot/check")
    assert r.status_code == 404


# ============ 列表 + status 过滤 ============


def test_list_issues_status_filter(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"issues": ['
            '{"kind": "X", "title": "A"}, {"kind": "X", "title": "B"}, {"kind": "X", "title": "C"}'
            ']}'
        ),
    )
    issues = client.post(f"/api/projects/{pid}/plot/check").json()["issues"]
    a, b, _c = issues

    # 把 A 改成 resolved,B 改成 dismissed,C 留 open
    client.patch(f"/api/issues/{a['id']}", json={"status": "resolved"})
    client.patch(f"/api/issues/{b['id']}", json={"status": "dismissed"})

    open_only = client.get(f"/api/projects/{pid}/issues?status=open").json()
    assert [i["title"] for i in open_only] == ["C"]

    resolved_only = client.get(f"/api/projects/{pid}/issues?status=resolved").json()
    assert [i["title"] for i in resolved_only] == ["A"]

    all_three = client.get(f"/api/projects/{pid}/issues").json()
    assert len(all_three) == 3


def test_open_count_endpoint(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    assert client.get(f"/api/projects/{pid}/issues/open-count").json() == {"count": 0}

    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"issues": [{"kind": "X", "title": "A"}, {"kind": "X", "title": "B"}]}'
        ),
    )
    issues = client.post(f"/api/projects/{pid}/plot/check").json()["issues"]
    assert client.get(f"/api/projects/{pid}/issues/open-count").json() == {"count": 2}

    client.patch(f"/api/issues/{issues[0]['id']}", json={"status": "resolved"})
    assert client.get(f"/api/projects/{pid}/issues/open-count").json() == {"count": 1}


# ============ 改 status / 删除 ============


def test_patch_status_validation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    monkeypatch.setattr(
        ai_client_module, "complete", _stub_complete('{"issues": [{"kind": "X", "title": "A"}]}')
    )
    iid = client.post(f"/api/projects/{pid}/plot/check").json()["issues"][0]["id"]

    # 合法
    r = client.patch(f"/api/issues/{iid}", json={"status": "dismissed"})
    assert r.status_code == 200
    assert r.json()["status"] == "dismissed"

    # 非法
    r = client.patch(f"/api/issues/{iid}", json={"status": "wat"})
    assert r.status_code == 422


def test_patch_unknown_issue_404(client: TestClient) -> None:
    r = client.patch("/api/issues/99999", json={"status": "resolved"})
    assert r.status_code == 404


def test_delete_issue(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    pid = _make_project(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete('{"issues": [{"kind": "X", "title": "A"}, {"kind": "X", "title": "B"}]}'),
    )
    issues = client.post(f"/api/projects/{pid}/plot/check").json()["issues"]
    assert client.delete(f"/api/issues/{issues[0]['id']}").status_code == 204
    remaining = client.get(f"/api/projects/{pid}/issues").json()
    assert len(remaining) == 1
    assert remaining[0]["title"] == "B"


def test_delete_unknown_issue_404(client: TestClient) -> None:
    r = client.delete("/api/issues/99999")
    assert r.status_code == 404


# ============ 删工程级联 ============


def test_delete_project_cascades_issues(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client)
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete('{"issues": [{"kind": "X", "title": "A"}]}'),
    )
    iid = client.post(f"/api/projects/{pid}/plot/check").json()["issues"][0]["id"]
    client.delete(f"/api/projects/{pid}")
    # 工程没了,issue 也得没
    assert client.patch(f"/api/issues/{iid}", json={"status": "resolved"}).status_code == 404
