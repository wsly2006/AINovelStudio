"""主线(PlotThread)+ 项目总纲注入测试。

ai_client.complete 用 monkeypatch 替成同步桩,避免真发起网络请求。
"""

from itertools import count

import pytest
from fastapi.testclient import TestClient

from app.ai import client as ai_client_module

_name_seq = count(1)


def _make_project(client: TestClient, **overrides) -> int:
    body = {"name": f"主线测试-{next(_name_seq)}"}
    body.update(overrides)
    r = client.post("/api/projects", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _stub_complete(payload: str):
    async def _fn(*args, **kwargs):
        return payload
    return _fn


# ============ CRUD ============


def test_create_thread(client: TestClient) -> None:
    pid = _make_project(client)
    r = client.post(
        f"/api/projects/{pid}/threads",
        json={
            "title": "男主复仇线",
            "description": "找出灭门凶手",
            "planned_arc": "起:被灭门 / 承:习武 / 转:得知真相 / 合:复仇",
            "importance": 5,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "男主复仇线"
    assert data["status"] == "planning"  # 默认值
    assert data["importance"] == 5


def test_thread_status_validation(client: TestClient) -> None:
    pid = _make_project(client)
    r = client.post(
        f"/api/projects/{pid}/threads",
        json={"title": "X", "status": "wat"},
    )
    assert r.status_code == 422


def test_list_threads_sorted_by_order(client: TestClient) -> None:
    pid = _make_project(client)
    # 不传 order_index,服务自动追加(1, 2, 3)
    for t in ["A", "B", "C"]:
        client.post(f"/api/projects/{pid}/threads", json={"title": t})
    titles = [t["title"] for t in client.get(f"/api/projects/{pid}/threads").json()]
    assert titles == ["A", "B", "C"]


def test_update_thread_status(client: TestClient) -> None:
    pid = _make_project(client)
    tid = client.post(
        f"/api/projects/{pid}/threads", json={"title": "X"}
    ).json()["id"]
    r = client.patch(f"/api/threads/{tid}", json={"status": "active"})
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_delete_thread(client: TestClient) -> None:
    pid = _make_project(client)
    tid = client.post(
        f"/api/projects/{pid}/threads", json={"title": "X"}
    ).json()["id"]
    assert client.delete(f"/api/threads/{tid}").status_code == 204
    assert client.patch(f"/api/threads/{tid}", json={"title": "Y"}).status_code == 404


def test_threads_unknown_project_404(client: TestClient) -> None:
    assert client.get("/api/projects/99999/threads").status_code == 404


# ============ Project synopsis 字段 ============


def test_project_synopsis_persists(client: TestClient) -> None:
    pid = _make_project(client, synopsis="本书讲述...最终主角与命运和解")
    p = client.get(f"/api/projects/{pid}").json()
    assert "和解" in p["synopsis"]

    # patch 也能更新
    r = client.patch(f"/api/projects/{pid}", json={"synopsis": "改过的总纲"})
    assert r.status_code == 200
    assert r.json()["synopsis"] == "改过的总纲"


# ============ AI 草拟主线 ============


def test_suggest_threads_creates_records(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client, synopsis="少年得宝物，登天阶")
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"threads": ['
            '{"title": "复仇线", "description": "找凶手", "planned_arc": "起承转合", "importance": 5},'
            '{"title": "成长线", "description": "学武", "planned_arc": "...", "importance": 4}'
            ']}'
        ),
    )
    r = client.post(f"/api/projects/{pid}/threads/suggest")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 2
    assert {t["title"] for t in data} == {"复仇线", "成长线"}
    # 全部入库为 planning 状态
    assert all(t["status"] == "planning" for t in data)


def test_suggest_threads_handles_markdown_wrapped_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client, synopsis="X")
    raw = (
        "好的:\n```json\n"
        '{"threads": [{"title": "线1", "description": "d", "planned_arc": "a", "importance": 3}]}'
        "\n```"
    )
    monkeypatch.setattr(ai_client_module, "complete", _stub_complete(raw))
    r = client.post(f"/api/projects/{pid}/threads/suggest")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_suggest_threads_clamps_out_of_range_importance(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client, synopsis="X")
    monkeypatch.setattr(
        ai_client_module,
        "complete",
        _stub_complete(
            '{"threads": [{"title": "T", "description": "", "planned_arc": "", "importance": 99}]}'
        ),
    )
    r = client.post(f"/api/projects/{pid}/threads/suggest")
    assert r.status_code == 200
    assert r.json()[0]["importance"] == 5


def test_suggest_threads_requires_synopsis_or_description(client: TestClient) -> None:
    pid = _make_project(client)  # 没有 synopsis 也没有 description
    r = client.post(f"/api/projects/{pid}/threads/suggest")
    assert r.status_code == 400
    assert "总纲" in r.json()["detail"] or "简介" in r.json()["detail"]


def test_suggest_threads_empty_payload_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = _make_project(client, synopsis="X")
    monkeypatch.setattr(
        ai_client_module, "complete", _stub_complete('{"threads": []}')
    )
    r = client.post(f"/api/projects/{pid}/threads/suggest")
    assert r.status_code == 502


# ============ Prompt 注入(关键回归):synopsis + 活跃主线 ============


def test_prompt_injects_synopsis_and_active_threads() -> None:
    """build_generate_messages 必须把 synopsis 和 planning/active 主线注入 user prompt。
    已 resolved 的主线不该出现。"""
    from types import SimpleNamespace

    from app.ai import prompts

    project = SimpleNamespace(
        name="测试书",
        genre="玄幻",
        description=None,
        synopsis="少年得宝,登天阶,最终守护人间。",
    )
    chapter = SimpleNamespace(id=1, order_index=1, title="开篇", content="", summary=None)
    threads = [
        SimpleNamespace(
            title="复仇线",
            description="灭门之仇",
            planned_arc="起承转合",
            status="active",
            importance=5,
        ),
        SimpleNamespace(
            title="情感线",
            description="与女主",
            planned_arc=None,
            status="planning",
            importance=3,
        ),
        # 已收的不该被传进来,但即便传了显示「已收束」也不会影响
        SimpleNamespace(
            title="师门线",
            description="X",
            planned_arc=None,
            status="resolved",
            importance=2,
        ),
    ]
    msgs = prompts.build_generate_messages(
        project, chapter, [], plot_threads=threads, target_word_count=3000, db=None
    )
    user_text = msgs[1]["content"]
    assert "少年得宝" in user_text
    assert "复仇线" in user_text
    assert "情感线" in user_text
    assert "师门线" in user_text  # service 层负责过滤,prompt 层信任传入


def test_prompt_omits_synopsis_block_when_empty() -> None:
    """没填 synopsis 时,user prompt 不应该残留「故事总纲」标题块。"""
    from types import SimpleNamespace

    from app.ai import prompts

    project = SimpleNamespace(
        name="X", genre=None, description=None, synopsis=None
    )
    chapter = SimpleNamespace(id=1, order_index=1, title="", content="", summary=None)
    msgs = prompts.build_generate_messages(
        project, chapter, [], target_word_count=3000, db=None
    )
    assert "故事总纲" not in msgs[1]["content"]
    assert "主线状态" not in msgs[1]["content"]
