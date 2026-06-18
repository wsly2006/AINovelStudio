"""AI 后台任务管理器:进程内注册表 + 事件队列。

设计要点:
- 任务在 asyncio.create_task 启动后立刻返回 task_id;HTTP 请求不再阻塞流式输出
- 每个任务维护一个 events 列表(完整历史)+ 一个 asyncio.Event(用于唤醒订阅者)
- 订阅者(SSE 端点)进入时先回放全部历史 events,再 await 新事件;
  这样断线/刷新重连后能完整看到从开始到当前的进度,不会漏帧
- 任务结束 / 失败 / 取消都会写一个终止事件(done/error/cancelled),订阅者据此关闭 SSE
- 任务记录保留一段时间(由 reaper 协程定期清理)避免内存泄漏

非目标:
- 不持久化到 DB,服务器重启所有 task 状态丢失(已落库的章节当然还在)
- 一次只允许一个进行中的 AI 任务,前端按钮 disable 控制(此处不强制)
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Literal

TaskStatus = Literal["running", "done", "error", "cancelled"]

# 任务结束后保留多久才被 reaper 清理(秒);留够用户刷新一次的时间
_RETAIN_AFTER_DONE_SEC = 30 * 60


@dataclass
class _Task:
    id: str
    project_id: int | None
    events: list[dict] = field(default_factory=list)
    status: TaskStatus = "running"
    notify: asyncio.Event = field(default_factory=asyncio.Event)
    handle: asyncio.Task | None = None
    finished_at: float | None = None  # 结束时间戳,reaper 用


_tasks: dict[str, _Task] = {}
_lock = asyncio.Lock()


def _new_id() -> str:
    return secrets.token_urlsafe(12)


async def register(project_id: int | None = None) -> _Task:
    async with _lock:
        t = _Task(id=_new_id(), project_id=project_id)
        _tasks[t.id] = t
        return t


async def get(task_id: str) -> _Task | None:
    async with _lock:
        return _tasks.get(task_id)


async def append_event(task_id: str, event: str, data: dict) -> None:
    """对外只暴露这一个写入口,确保 events 与 notify 同步。"""
    t = _tasks.get(task_id)
    if t is None:
        return
    t.events.append({"event": event, "data": data})
    t.notify.set()


async def finish(task_id: str, status: TaskStatus, message: str | None = None) -> None:
    t = _tasks.get(task_id)
    if t is None:
        return
    t.status = status
    t.finished_at = time.monotonic()
    # 结束帧也走 events,订阅者读到这一帧就知道流结束
    if status == "done":
        evt = {"event": "done", "data": {}}
    elif status == "cancelled":
        evt = {"event": "cancelled", "data": {"message": message or "已取消"}}
    else:
        evt = {"event": "error", "data": {"message": message or "未知错误"}}
    t.events.append(evt)
    t.notify.set()


async def cancel(task_id: str) -> bool:
    """取消运行中的任务;已结束的任务返回 False。"""
    t = _tasks.get(task_id)
    if t is None or t.status != "running":
        return False
    if t.handle is not None and not t.handle.done():
        t.handle.cancel()
    return True


async def stream(task_id: str):
    """异步迭代:先回放历史事件,再 tail 直到任务结束。"""
    t = _tasks.get(task_id)
    if t is None:
        return
    cursor = 0
    while True:
        # 当前可见的所有事件先吐出
        while cursor < len(t.events):
            yield t.events[cursor]
            cursor += 1
        # 任务已经结束并且事件都吐完了,关闭流
        if t.status != "running":
            return
        # 等下一帧
        t.notify.clear()
        try:
            await t.notify.wait()
        except asyncio.CancelledError:
            return


async def reaper_loop(interval_sec: float = 60.0) -> None:
    """定期清理早已结束的 task 记录,避免长跑进程内存堆积。"""
    while True:
        try:
            await asyncio.sleep(interval_sec)
            now = time.monotonic()
            stale: list[str] = []
            async with _lock:
                for tid, t in _tasks.items():
                    if (
                        t.status != "running"
                        and t.finished_at is not None
                        and now - t.finished_at > _RETAIN_AFTER_DONE_SEC
                    ):
                        stale.append(tid)
                for tid in stale:
                    _tasks.pop(tid, None)
        except asyncio.CancelledError:
            return
        except Exception:
            # reaper 不能因单次异常退出,否则后续永远不再清理
            continue
