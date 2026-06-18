from fastapi.testclient import TestClient


def _setup(client: TestClient) -> dict:
    pid = client.post("/api/projects", json={"name": "T", "genre": "xianxia"}).json()["id"]
    c1 = client.post(f"/api/projects/{pid}/chapters", json={"title": "C1"}).json()["id"]
    h1 = client.post(f"/api/projects/{pid}/characters", json={"name": "甲"}).json()["id"]
    h2 = client.post(f"/api/projects/{pid}/characters", json={"name": "乙"}).json()["id"]
    return {"pid": pid, "c1": c1, "h1": h1, "h2": h2}


def test_create_task(client: TestClient) -> None:
    s = _setup(client)
    r = client.post(
        f"/api/projects/{s['pid']}/tasks",
        json={
            "title": "夺回玄铁剑",
            "description": "一定要拿回来",
            "status": "in_progress",
            "priority": 4,
            "assignee_ids": [s["h1"]],
            "started_chapter_id": s["c1"],
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "夺回玄铁剑"
    assert body["assignee_ids"] == [s["h1"]]


def test_assignee_must_belong_project(client: TestClient) -> None:
    """跨工程的 character_id 应被静默剔除。"""
    s = _setup(client)
    pid2 = client.post("/api/projects", json={"name": "其他"}).json()["id"]
    other = client.post(f"/api/projects/{pid2}/characters", json={"name": "外"}).json()["id"]
    r = client.post(
        f"/api/projects/{s['pid']}/tasks",
        json={"title": "X", "assignee_ids": [s["h1"], other]},
    )
    assert r.status_code == 201
    # 跨工程的 other 被剔除
    assert r.json()["assignee_ids"] == [s["h1"]]


def test_status_filter(client: TestClient) -> None:
    s = _setup(client)
    client.post(f"/api/projects/{s['pid']}/tasks", json={"title": "P", "status": "pending"})
    client.post(
        f"/api/projects/{s['pid']}/tasks",
        json={"title": "I", "status": "in_progress"},
    )
    client.post(f"/api/projects/{s['pid']}/tasks", json={"title": "D", "status": "done"})

    pending = client.get(f"/api/projects/{s['pid']}/tasks?status_filter=pending").json()
    assert [t["title"] for t in pending] == ["P"]

    in_progress = client.get(
        f"/api/projects/{s['pid']}/tasks?status_filter=in_progress"
    ).json()
    assert [t["title"] for t in in_progress] == ["I"]


def test_list_sorts_in_progress_first(client: TestClient) -> None:
    s = _setup(client)
    client.post(f"/api/projects/{s['pid']}/tasks", json={"title": "P", "priority": 5})
    client.post(
        f"/api/projects/{s['pid']}/tasks",
        json={"title": "I", "status": "in_progress", "priority": 2},
    )
    listed = client.get(f"/api/projects/{s['pid']}/tasks").json()
    # in_progress 排在前(尽管优先级低)
    assert listed[0]["title"] == "I"


def test_update_delete(client: TestClient) -> None:
    s = _setup(client)
    tid = client.post(
        f"/api/projects/{s['pid']}/tasks", json={"title": "原"}
    ).json()["id"]

    r = client.patch(
        f"/api/tasks/{tid}",
        json={"status": "done", "finished_chapter_id": s["c1"]},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert r.json()["finished_chapter_id"] == s["c1"]

    assert client.delete(f"/api/tasks/{tid}").status_code == 204


def test_cascade_delete_with_project(client: TestClient) -> None:
    s = _setup(client)
    tid = client.post(
        f"/api/projects/{s['pid']}/tasks", json={"title": "X"}
    ).json()["id"]
    assert client.delete(f"/api/projects/{s['pid']}").status_code == 204
    assert client.patch(f"/api/tasks/{tid}", json={}).status_code == 404


def test_export_import_roundtrip(client: TestClient) -> None:
    s = _setup(client)
    client.post(
        f"/api/projects/{s['pid']}/tasks",
        json={
            "title": "复仇",
            "status": "in_progress",
            "priority": 5,
            "assignee_ids": [s["h1"]],
            "started_chapter_id": s["c1"],
        },
    )
    exported = client.get(f"/api/projects/{s['pid']}/export.json").json()
    assert "tasks" in exported
    assert exported["tasks"][0]["title"] == "复仇"

    files = {
        "file": (
            "e.json",
            __import__("json").dumps(exported).encode("utf-8"),
            "application/json",
        )
    }
    r = client.post("/api/projects/import", files=files)
    assert r.status_code == 201
    new_pid = r.json()["id"]
    new_tasks = client.get(f"/api/projects/{new_pid}/tasks").json()
    assert len(new_tasks) == 1
    assert new_tasks[0]["title"] == "复仇"
    assert new_tasks[0]["status"] == "in_progress"
    # assignee 与 chapter 都重映射上了
    assert len(new_tasks[0]["assignee_ids"]) == 1


def test_active_task_injection_in_prompt() -> None:
    """单测 prompts._tasks_context:有任务时注入,无则不污染。"""
    from app.ai import prompts
    from app.models.task import Task

    t = Task(
        id=1, project_id=1, title="夺回玄铁剑", description="必须拿回来",
        status="in_progress", priority=5, assignee_ids=[1],
        started_chapter_id=None, finished_chapter_id=None,
    )
    text = prompts._tasks_context([t], {1: "李逍遥"})
    assert "进行中的任务" in text
    assert "夺回玄铁剑" in text
    assert "李逍遥" in text
    assert "紧急" in text  # priority=5 → 紧急

    assert prompts._tasks_context([], {}) == ""
