"""AI 起书名 / 生简介:都是一次性同步调用,直接走 ai_client.complete。

输入是一个轻量「设定快照」,字段与 ProjectCreate 重合但全可选——
新建工程对话框里用户可能只填了部分,服务侧把现有信息拼成 outline_meta 块,
让模型基于已知线索去补另一个字段(没填书名时给名,没填简介时给介绍)。
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.services import prompt_service

# 行首的编号 / 项目符号:`1.` `1、` `1)` `(1)` `·` `-` 等等
_LINE_PREFIX_RE = re.compile(r"^\s*(?:[\(（]?\d+[\)）\.\、:]|[·•\-—\*])\s*")
# 收尾把书名号 / 双引号去掉
_WRAP_CHARS = "《》〈〉「」『』\"'“”‘’"


def _build_outline_meta(
    *,
    name: str | None,
    description: str | None,
    channel: str | None,
    genre: str | None,
    tags: list[str] | None,
) -> str:
    parts: list[str] = []
    if name:
        parts.append(f"暂定书名:{name}")
    if description:
        parts.append(f"内容简介:{description}")
    if channel:
        parts.append(f"频道:{channel}")
    if genre:
        parts.append(f"题材:{genre}")
    if tags:
        parts.append(f"标签:{', '.join(tags)}")
    if not parts:
        # 用户什么都没填,给模型一个最低限度的占位,避免空 prompt
        parts.append("(用户尚未填写任何设定,请发挥想象,生成大众向网文风格的候选)")
    return "\n".join(parts)


def _parse_titles(text: str, limit: int = 5) -> list[str]:
    """每行一个书名,容忍模型输出编号 / 项目符号 / 书名号。

    去重后保留顺序,超过 limit 截断。
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in text.splitlines():
        line = _LINE_PREFIX_RE.sub("", raw).strip().strip(_WRAP_CHARS).strip()
        if not line:
            continue
        # 偶尔模型会在一行里塞副标题,用「:」「——」截断只取主标题
        for sep in ("——", "—", " - ", ":", ":"):
            if sep in line:
                line = line.split(sep, 1)[0].strip()
                break
        if not line or len(line) > 24:
            continue
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
        if len(out) >= limit:
            break
    return out


async def suggest_titles(
    db: Session,
    *,
    name: str | None,
    description: str | None,
    channel: str | None,
    genre: str | None,
    tags: list[str] | None,
) -> list[str]:
    messages = prompt_service.render(
        db,
        "project.suggest_title",
        {
            "outline_meta": _build_outline_meta(
                name=name, description=description, channel=channel, genre=genre, tags=tags,
            ),
        },
    )
    text = await ai_client.complete(db, messages, scene="project.suggest_title", max_tokens=400)
    titles = _parse_titles(text, limit=5)
    if not titles:
        # 模型偶尔无视换行约定整段输出,兜底切一下
        titles = [t.strip() for t in re.split(r"[、,，\s]+", text) if t.strip()][:5]
    return titles


async def suggest_description(
    db: Session,
    *,
    name: str | None,
    description: str | None,
    channel: str | None,
    genre: str | None,
    tags: list[str] | None,
) -> str:
    messages = prompt_service.render(
        db,
        "project.suggest_description",
        {
            "outline_meta": _build_outline_meta(
                name=name, description=description, channel=channel, genre=genre, tags=tags,
            ),
        },
    )
    text = await ai_client.complete(db, messages, scene="project.suggest_description", max_tokens=600)
    return text.strip().strip(_WRAP_CHARS).strip()


__all__ = ["suggest_titles", "suggest_description"]
