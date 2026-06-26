"""ai_task_manager 单元测试。

只测时序与状态机,不依赖 FastAPI / DB。
模块级 _tasks 字典是进程内共享状态,每个用例前清空。
"""

import asyncio

import pytest

from app.services import ai_task_manager as tm


@pytest.fixture(autouse=True)
def _reset_registry():
    """模块级注册表是进程共享的,每个测试前清空。"""
    tm._tasks.clear()
    yield
    tm._tasks.clear()


async def test_register_assigns_unique_ids() -> None:
    t1 = await tm.register(project_id=1)
    t2 = await tm.register(project_id=1)
    assert t1.id != t2.id
    assert t1.status == "running"
    assert t1.finished_at is None
    # 注册表里能查到
    got = await tm.get(t1.id)
    assert got is t1


async def test_append_event_stores_in_order() -> None:
    t = await tm.register()
    await tm.append_event(t.id, "progress", {"i": 1})
    await tm.append_event(t.id, "progress", {"i": 2})
    assert [e["data"]["i"] for e in t.events] == [1, 2]


async def test_append_event_on_unknown_task_silently_skips() -> None:
    """工程不存在的 task_id 不该抛错,只是 no-op —— 这是 finish/append 的安全保证。"""
    await tm.append_event("nonexistent", "progress", {})
    # 不抛异常即通过


async def test_finish_done_emits_terminal_event() -> None:
    t = await tm.register()
    await tm.append_event(t.id, "progress", {"i": 1})
    await tm.finish(t.id, "done")
    assert t.status == "done"
    assert t.finished_at is not None
    # 最后一帧是 done 事件
    assert t.events[-1] == {"event": "done", "data": {}}


async def test_finish_error_carries_message() -> None:
    t = await tm.register()
    await tm.finish(t.id, "error", "boom")
    assert t.status == "error"
    assert t.events[-1] == {"event": "error", "data": {"message": "boom"}}


async def test_finish_cancelled_uses_default_message() -> None:
    t = await tm.register()
    await tm.finish(t.id, "cancelled")
    assert t.status == "cancelled"
    assert t.events[-1] == {"event": "cancelled", "data": {"message": "已取消"}}


async def test_stream_replays_history_then_terminates() -> None:
    """订阅者进来时任务已经有历史 + 已结束 → 一次性吐出所有事件后退出。"""
    t = await tm.register()
    await tm.append_event(t.id, "progress", {"i": 1})
    await tm.append_event(t.id, "progress", {"i": 2})
    await tm.finish(t.id, "done")

    seen: list[dict] = []
    async for evt in tm.stream(t.id):
        seen.append(evt)
    assert [e["event"] for e in seen] == ["progress", "progress", "done"]


async def test_stream_unknown_task_returns_empty() -> None:
    seen = [evt async for evt in tm.stream("nonexistent")]
    assert seen == []


async def test_stream_tails_live_events() -> None:
    """订阅者在任务进行中开始读 → 边产生边收到,最后看到 done 后退出。"""
    t = await tm.register()
    received: list[dict] = []

    async def producer() -> None:
        for i in range(3):
            await asyncio.sleep(0.01)
            await tm.append_event(t.id, "progress", {"i": i})
        await asyncio.sleep(0.01)
        await tm.finish(t.id, "done")

    async def consumer() -> None:
        async for evt in tm.stream(t.id):
            received.append(evt)

    await asyncio.gather(producer(), consumer())
    assert [e["event"] for e in received] == ["progress", "progress", "progress", "done"]
    assert [e["data"].get("i") for e in received[:3]] == [0, 1, 2]


async def test_two_concurrent_subscribers_both_see_full_history() -> None:
    """断线重连场景:两个订阅者同时看一个任务,各自都拿到完整事件流。

    实现细节:每个 stream() 协程维护自己的 cursor,共享 t.notify 唤醒;
    最后一个 notify.clear 不会让先到的订阅者错过事件,因为下次进循环时
    还会先把 events[cursor:] 吐完才 await。
    """
    t = await tm.register()
    a_events: list[dict] = []
    b_events: list[dict] = []

    async def producer() -> None:
        for i in range(3):
            await asyncio.sleep(0.005)
            await tm.append_event(t.id, "tick", {"i": i})
        await tm.finish(t.id, "done")

    async def consume(bucket: list[dict]) -> None:
        async for evt in tm.stream(t.id):
            bucket.append(evt)

    await asyncio.gather(consume(a_events), consume(b_events), producer())
    assert [e["event"] for e in a_events] == ["tick", "tick", "tick", "done"]
    assert [e["event"] for e in b_events] == ["tick", "tick", "tick", "done"]


async def test_cancel_running_task_invokes_handle_cancel() -> None:
    t = await tm.register()

    # 挂一个会被 cancel 的真协程任务
    async def _long_runner() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            # 业务编排器(auto_writer / project_ai)在 CancelledError 分支会写 finish
            await tm.finish(t.id, "cancelled")
            raise

    t.handle = asyncio.create_task(_long_runner())
    # 给协程一个调度机会进入 sleep
    await asyncio.sleep(0)

    ok = await tm.cancel(t.id)
    assert ok is True
    # 等业务协程跑完 cancelled 分支
    with pytest.raises(asyncio.CancelledError):
        await t.handle
    assert t.status == "cancelled"


async def test_cancel_finished_task_returns_false() -> None:
    t = await tm.register()
    await tm.finish(t.id, "done")
    ok = await tm.cancel(t.id)
    assert ok is False


async def test_cancel_unknown_task_returns_false() -> None:
    assert await tm.cancel("nonexistent") is False


async def test_reaper_evicts_old_finished_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """把保留窗口压到 0,起一轮 reaper 应当把已结束任务清掉,running 任务保留。"""
    # 缩短保留窗,让本次 finish 立刻算「过期」
    monkeypatch.setattr(tm, "_RETAIN_AFTER_DONE_SEC", 0.0)

    done_task = await tm.register()
    await tm.finish(done_task.id, "done")

    running_task = await tm.register()  # 故意不结束

    # 起 reaper,1ms 跑一次,等几个 tick 就杀掉
    reaper = asyncio.create_task(tm.reaper_loop(interval_sec=0.001))
    # 给 reaper 几个调度机会
    for _ in range(20):
        await asyncio.sleep(0.001)
        if done_task.id not in tm._tasks:
            break

    reaper.cancel()
    try:
        await reaper
    except asyncio.CancelledError:
        pass

    assert done_task.id not in tm._tasks
    assert running_task.id in tm._tasks


async def test_reaper_survives_per_iteration_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """reaper 单轮抛错不应让协程整体退出,否则后续永远不再清理。"""
    monkeypatch.setattr(tm, "_RETAIN_AFTER_DONE_SEC", 0.0)

    # 先把数据准备好,再换 lock —— 否则 register/finish 也会撞上 boom
    done_task = await tm.register()
    await tm.finish(done_task.id, "done")

    # 让第一次拿锁(必然是 reaper 第一轮)抛错,后续正常
    real_lock = tm._lock
    call_count = {"n": 0}

    class _BoomLock:
        async def __aenter__(self):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated transient failure")
            return await real_lock.__aenter__()

        async def __aexit__(self, *args):
            return await real_lock.__aexit__(*args)

    monkeypatch.setattr(tm, "_lock", _BoomLock())

    reaper = asyncio.create_task(tm.reaper_loop(interval_sec=0.001))
    # 等到第二轮:第一轮抛错被吞,第二轮应当成功清理
    for _ in range(40):
        await asyncio.sleep(0.001)
        if done_task.id not in tm._tasks:
            break

    reaper.cancel()
    try:
        await reaper
    except asyncio.CancelledError:
        pass

    assert done_task.id not in tm._tasks
    assert call_count["n"] >= 2  # 确认 reaper 真的跑了不止一轮
