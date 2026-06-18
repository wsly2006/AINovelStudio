"""AI 创建工程:基于书名 / 简介 / 题材 / 标签 / 字数 / 章节数,
作为后台任务流式生成每章副标题与概要,边生成边落库。

以 task_id 模式运行:
    1. 调用方先 register 一个 task,得到 task_id
    2. 把 run_in_background(task_id, payload) 丢进 asyncio.create_task
    3. SSE 端点用 ai_task_manager.stream(task_id) 订阅事件
    4. 任务自管 DB session,因为 HTTP 请求作用域早就结束了

事件协议(全部由本模块通过 ai_task_manager.append_event 写入):
    start    : {project_id, name, total}
    progress : {index, total, title, order_index}
    done     : {project_id, name, chapter_count}
    error    : {message}
    cancelled: {message}
"""

from __future__ import annotations

import asyncio
import json
import re

from app.ai import client as ai_client
from app.ai.client import AIError, AINotConfiguredError
from app.database import SessionLocal
from app.schemas.chapter import ChapterCreate
from app.schemas.project import ProjectCreate
from app.services import ai_task_manager, chapter_service, project_service, prompt_service
from app.services.project_service import ProjectNameConflictError


_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```\s*$", re.MULTILINE)


def _build_messages(
    *,
    name: str,
    description: str | None,
    channel: str | None,
    genre: str | None,
    tags: list[str],
    target_word_count: int,
    chapter_count: int,
    db=None,
) -> list[dict]:
    avg = max(target_word_count // max(chapter_count, 1), 500)
    parts: list[str] = [
        f"小说名:{name}",
        f"目标总字数:约 {target_word_count} 字",
        f"章节数:{chapter_count} 章(平均每章约 {avg} 字)",
    ]
    if description:
        parts.append(f"内容简介:{description}")
    if channel:
        parts.append(f"频道:{channel}")
    if genre:
        parts.append(f"题材:{genre}")
    if tags:
        parts.append(f"标签:{', '.join(tags)}")

    return prompt_service.render(
        db,
        "project.outline",
        {
            "outline_meta": "\n".join(parts),
            "chapter_count": str(chapter_count),
        },
    )


def _try_parse_line(line: str) -> dict | None:
    """容忍 AI 偶尔输出 ```json``` 围栏或前后多余的非 JSON 行。"""
    line = line.strip()
    if not line or line.startswith("```"):
        return None
    l = line.find("{")
    r = line.rfind("}")
    if l < 0 or r <= l:
        return None
    try:
        obj = json.loads(line[l : r + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    title = str(obj.get("title", "")).strip()
    summary = str(obj.get("summary", "")).strip() or None
    return {"title": title, "summary": summary}


async def create_project_sync(payload: ProjectCreate) -> tuple[int, str]:
    """同步建工程,失败直接抛;返回 (project_id, name)。

    这一步必须在 register task 之前完成,这样 task_id 一返回前端就有 project_id。
    """
    db = SessionLocal()
    try:
        project = project_service.create_project(db, payload)
        return project.id, project.name
    finally:
        db.close()


async def run_generation(
    task_id: str,
    *,
    project_id: int,
    project_name: str,
    project_payload: ProjectCreate,
    target_word_count: int,
    chapter_count: int,
) -> None:
    """后台 task 主体。所有事件都通过 ai_task_manager 写入,自己捕获所有异常。"""
    await ai_task_manager.append_event(
        task_id,
        "start",
        {"project_id": project_id, "name": project_name, "total": chapter_count},
    )

    db = SessionLocal()
    try:
        messages = _build_messages(
            name=project_payload.name,
            description=project_payload.description,
            channel=project_payload.channel,
            genre=project_payload.genre,
            tags=list(project_payload.tags or []),
            target_word_count=target_word_count,
            chapter_count=chapter_count,
            db=db,
        )

        buffer = ""
        created = 0

        # 默认 max_tokens(常见 4096)对 20+ 章不够,会在第 10 章左右截断;
        # 按每章 350 token 估算 + 500 buffer,上限 32000
        outline_max_tokens = min(chapter_count * 350 + 500, 32000)

        async for delta in ai_client.stream_chat(
            db, messages, scene="project.outline", project_id=project_id,
            max_tokens=outline_max_tokens,
        ):
            buffer += delta
            while True:
                nl = buffer.find("\n")
                if nl < 0:
                    break
                line, buffer = buffer[:nl], buffer[nl + 1 :]
                parsed = _try_parse_line(line)
                if parsed is None:
                    continue
                chapter = chapter_service.create_chapter(
                    db,
                    project_id,
                    ChapterCreate(title=parsed["title"], summary=parsed["summary"]),
                )
                created += 1
                await ai_task_manager.append_event(
                    task_id,
                    "progress",
                    {
                        "index": created,
                        "total": chapter_count,
                        "title": parsed["title"],
                        "order_index": chapter.order_index,
                    },
                )
                if created >= chapter_count:
                    buffer = ""
                    break
            if created >= chapter_count:
                break

        # 兜底:流结束后 buffer 里还可能有最后一行没换行
        if created < chapter_count and buffer.strip():
            cleaned = _FENCE_RE.sub("", buffer)
            for line in cleaned.splitlines():
                if created >= chapter_count:
                    break
                parsed = _try_parse_line(line)
                if parsed is None:
                    continue
                chapter = chapter_service.create_chapter(
                    db,
                    project_id,
                    ChapterCreate(title=parsed["title"], summary=parsed["summary"]),
                )
                created += 1
                await ai_task_manager.append_event(
                    task_id,
                    "progress",
                    {
                        "index": created,
                        "total": chapter_count,
                        "title": parsed["title"],
                        "order_index": chapter.order_index,
                    },
                )

        await ai_task_manager.append_event(
            task_id,
            "result",
            {
                "project_id": project_id,
                "name": project_name,
                "chapter_count": created,
            },
        )
        await ai_task_manager.finish(task_id, "done")
    except asyncio.CancelledError:
        # 用户取消;不再补 chapter,把当前进度凝固住
        await ai_task_manager.finish(task_id, "cancelled")
        raise
    except (AINotConfiguredError, AIError) as e:
        await ai_task_manager.finish(task_id, "error", str(e))
    except Exception as e:  # noqa: BLE001 — 后台 task 必须吃掉所有异常,否则进程崩
        await ai_task_manager.finish(task_id, "error", str(e))
    finally:
        db.close()


async def start_background(
    *,
    project_payload: ProjectCreate,
    target_word_count: int,
    chapter_count: int,
) -> tuple[str, int]:
    """对外入口:同步建工程 → 注册 task → 启动后台协程 → 返回 (task_id, project_id)。"""
    project_id, project_name = await create_project_sync(project_payload)

    task = await ai_task_manager.register(project_id=project_id)
    coro = run_generation(
        task.id,
        project_id=project_id,
        project_name=project_name,
        project_payload=project_payload,
        target_word_count=target_word_count,
        chapter_count=chapter_count,
    )
    task.handle = asyncio.create_task(coro)
    return task.id, project_id


__all__ = [
    "ProjectNameConflictError",
    "start_background",
]
