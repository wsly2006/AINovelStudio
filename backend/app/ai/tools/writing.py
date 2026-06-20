"""写作上下文聚合工具 — Phase 4。

只暴露一个工具 get_writing_context,把分散的人物档案 / 本章前快照 /
最近情节 / 世界观 / 进行中任务一次性吐出来,让 Claude 写得有依据。
"""

from __future__ import annotations

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.services import writing_context_service


@tool(category="writing")
@friendly_errors
def get_writing_context(
    chapter_id: int,
    character_ids: list[int] | None = None,
    world_entity_ids: list[int] | None = None,
    item_ids: list[int] | None = None,
) -> dict:
    """把"为这一章下笔需要的全部背景"一次性聚合返回。

    在动手写正文之前调一次,Claude 拿到结构化的 JSON 自己组织表达,
    无需再来回查多个工具。

    返回的字段:
    - project: 工程基本盘(类型、频道、tags、简介、大纲)
    - chapter: 当前章节元信息(标题、order_index、摘要、节拍 beats)
    - previous_chapters: 前序章节(摘要为主,无摘要时给 80 字开头节选)
    - characters: 参与人物档案 + 本章开始前的状态快照
      (境界 / 所在地点 / 持有物品 / 伤情 — 来自事件溯源)
    - recent_events: 最近 12 个情节事件(按章节顺序)
    - world_entities: 相关地点 / 组织 / 概念
    - items: 相关物品(独立 items 表)
    - active_tasks: 涉及参与人物的进行中任务(寻师/复仇/夺物/...)
      可作为推动情节的钩子

    参数:
    - chapter_id: 在写哪一章(必填)— 决定快照截止点
    - character_ids / world_entity_ids / item_ids: 本章会出现的元素 id 列表
      不传或传空就不带对应数据,粒度由调用者控制(避免 token 爆炸)

    通常用法:
        ctx = get_writing_context(
            chapter_id=12,
            character_ids=[3, 7],          # 主角 + 这章新出场的反派
            world_entity_ids=[14],         # 这章主要场景
        )
        # 拿到 ctx 后自己组织 prompt,写正文,再调 update_chapter 落库
    """
    with with_db() as db:
        ctx = writing_context_service.assemble(
            db,
            chapter_id,
            character_ids=character_ids,
            world_entity_ids=world_entity_ids,
            item_ids=item_ids,
        )
        return ctx.to_dict()
