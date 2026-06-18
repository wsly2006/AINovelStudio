"""Prompt 模板:对外暴露 build_xxx_messages,内部走 prompt_service 渲染。

各 build_xxx 函数把上下文块文本算好后,通过 prompt_service.render(db, key, values)
拿到 messages。db 可为 None(测试 / 无 db 调用),此时自动回落注册表里的默认模板。
"""

from app.models.chapter import Chapter
from app.models.character import Character
from app.models.item import Item
from app.models.plot_event import PlotEvent
from app.models.plot_thread import PlotThread
from app.models.project import Project
from app.models.task import Task
from app.models.world_entity import WorldEntity
from app.services import prompt_service

_KIND_LABEL = {
    "location": "地点",
    "organization": "组织",
    "concept": "概念",
}


def _beats_context(beats: list[dict] | None, target_word_count: int | None = None) -> str:
    """章节节拍块。AI 写正文时按这些拍展开,每拍≈ target/N 字。

    beats 形状(从 Chapter.beats JSON 列读出):
        [{"title": "...", "detail": "...", "thread_titles": ["复仇线"]}]
    旧章节没有节拍 → 返回空字符串,prompt 里那块就消失。
    """
    if not beats:
        return ""
    n = len([b for b in beats if (b.get("title") or "").strip()])
    if not n:
        return ""
    head = "本章节拍(必须按下面的顺序与意图展开,不要跳拍、不要加额外大段落):"
    if target_word_count and n > 0:
        per = max(200, target_word_count // n)
        head += f"\n每拍约 {per} 字,可上下浮动。"
    lines = [head]
    for i, b in enumerate(beats, start=1):
        title = (b.get("title") or "").strip()
        if not title:
            continue
        detail = (b.get("detail") or "").strip()
        threads = b.get("thread_titles") or []
        bits = []
        if detail:
            bits.append(detail)
        if threads:
            bits.append("推进:" + "、".join(t for t in threads if t))
        body = " / ".join(bits)
        lines.append(f"{i}. {title}{ ' — ' + body if body else '' }")
    return "\n".join(lines)


def _project_context(project: Project) -> str:
    parts = [f"《{project.name}》"]
    if project.genre:
        parts.append(f"类型:{project.genre}")
    if project.description:
        parts.append(f"简介:{project.description}")
    return " / ".join(parts)


def _synopsis_context(project: Project) -> str:
    """项目总纲块。AI 写每一章都要看到「整本书该走向哪里」,这是最强的全局锚。"""
    text = (project.synopsis or "").strip()
    if not text:
        return ""
    return f"故事总纲(贯穿全书的走向与结局,本章不应偏离此主线):\n{text}"


_THREAD_STATUS_LABEL = {
    "planning": "规划中",
    "active": "进行中",
    "resolved": "已收束",
    "abandoned": "已废弃",
}


def _threads_context(threads: list[PlotThread]) -> str:
    """主线状态块。只列 planning + active,已收 / 废弃不再喂回去。"""
    if not threads:
        return ""
    lines = [
        "主线状态(本章应推进其中至少一条;已规划但未启动的伏笔注意按计划埋点):"
    ]
    for t in threads:
        label = _THREAD_STATUS_LABEL.get(t.status, t.status)
        head = f"【{label}】《{t.title}》"
        if t.importance and t.importance >= 4:
            head += "★"
        bits = []
        if t.description:
            bits.append(t.description.strip())
        if t.planned_arc:
            bits.append(f"走向:{t.planned_arc.strip()}")
        body = " / ".join(bits)
        lines.append(f"- {head}{ '。' + body if body else '' }")
    return "\n".join(lines)


def _chapter_label(chapter: Chapter) -> str:
    """章节统一标签:「第 N 章 副标题」(无副标题则只保留前缀)。"""
    sub = (chapter.title or "").strip()
    base = f"第 {chapter.order_index} 章"
    return f"{base}《{sub}》" if sub else base


def _previous_chapters_context(chapters: list[Chapter], current_id: int | None) -> str:
    lines = []
    for c in chapters:
        if current_id is not None and c.id == current_id:
            break
        label = _chapter_label(c)
        if c.summary:
            lines.append(f"- {label}: {c.summary}")
        else:
            preview = (c.content or "").strip().replace("\n", " ")[:80]
            if preview:
                lines.append(f"- {label}(节选): {preview}…")
    return "\n".join(lines) if lines else "(无前序章节)"


def _characters_context(
    characters: list[Character],
    snapshots_by_id: dict[int, dict] | None = None,
) -> str:
    if not characters:
        return ""
    snaps = snapshots_by_id or {}
    lines = ["参与人物档案(请保持其形象、性格、说话方式一致):"]
    for c in characters:
        bits = []
        aliases = "、".join(c.aliases or [])
        if aliases:
            bits.append(f"别名:{aliases}")
        if c.role:
            bits.append(f"定位:{c.role}")
        if c.profile:
            bits.append(f"概述:{c.profile}")
        if c.appearance:
            bits.append(f"外貌:{c.appearance}")
        if c.personality:
            bits.append(f"性格:{c.personality}")
        if c.background:
            bits.append(f"背景:{c.background}")

        snap = snaps.get(c.id)
        if snap:
            state_bits = []
            if snap.get("tier_label"):
                state_bits.append(f"当前境界:{snap['tier_label']}")
            if snap.get("location_name"):
                state_bits.append(f"所在地点:{snap['location_name']}")
            if snap.get("item_names"):
                state_bits.append(f"持有物品:{ '、'.join(snap['item_names']) }")
            if snap.get("injuries"):
                state_bits.append(f"伤情:{ '、'.join(snap['injuries']) }")
            if state_bits:
                bits.append("[本章开始前状态] " + " / ".join(state_bits))

        body = " / ".join(bits) if bits else "(暂无详情)"
        lines.append(f"- {c.name}:{body}")
    return "\n".join(lines)


def _recent_events_context(events: list[PlotEvent], chapters: list[Chapter]) -> str:
    if not events:
        return ""
    chap_index = {c.id: c for c in chapters}
    lines = ["最近的情节脉络(按章节顺序):"]
    for ev in events:
        chap = chap_index.get(ev.chapter_id)
        chap_label = f"第 {chap.order_index} 章" if chap else f"章节 #{ev.chapter_id}"
        desc = (ev.description or "").strip()
        if desc:
            lines.append(f"- {chap_label}「{ev.title}」:{desc}")
        else:
            lines.append(f"- {chap_label}「{ev.title}」")
    return "\n".join(lines)


def _world_context(entities: list[WorldEntity]) -> str:
    if not entities:
        return ""
    by_kind: dict[str, list[WorldEntity]] = {}
    for e in entities:
        by_kind.setdefault(e.kind, []).append(e)

    blocks = ["世界观设定(请保持其内涵一致,沿用其名称):"]
    for kind, items in by_kind.items():
        blocks.append(f"【{_KIND_LABEL.get(kind, kind)}】")
        for e in items:
            bits = []
            if e.aliases:
                bits.append(f"别名:{ '、'.join(e.aliases) }")
            if e.summary:
                bits.append(e.summary)
            elif e.description:
                bits.append(e.description.split("\n", 1)[0][:120])
            line = f"- {e.name}"
            if bits:
                line += f":{ ' / '.join(bits) }"
            blocks.append(line)
    return "\n".join(blocks)


def _items_context(items: list[Item]) -> str:
    if not items:
        return ""
    lines = ["相关物品(请保持其名称、功能一致):"]
    for it in items:
        bits = []
        if it.aliases:
            bits.append(f"别名:{ '、'.join(it.aliases) }")
        if it.summary:
            bits.append(it.summary)
        elif it.description:
            bits.append(it.description.split("\n", 1)[0][:120])
        line = f"- {it.name}"
        if bits:
            line += f":{ ' / '.join(bits) }"
        lines.append(line)
    return "\n".join(lines)


_PRIORITY_LABELS = {1: "低", 2: "中", 3: "中高", 4: "高", 5: "紧急"}


def _tasks_context(tasks: list[Task], char_names: dict[int, str]) -> str:
    if not tasks:
        return ""
    lines = ["进行中的任务(可作为本章推动情节的钩子):"]
    for t in tasks:
        bits = []
        bits.append(f"[优先级:{_PRIORITY_LABELS.get(t.priority, '中')}]")
        if t.status == "in_progress":
            bits.append("已开始")
        if t.assignee_ids:
            names = [char_names[c] for c in t.assignee_ids if c in char_names]
            if names:
                bits.append(f"担当:{ '、'.join(names) }")
        prefix = " ".join(bits)
        line = f"- {prefix} 「{t.title}」"
        if t.description:
            line += f":{t.description.strip()[:120]}"
        lines.append(line)
    return "\n".join(lines)


def _extra_instruction_block(extra: str | None) -> str:
    return f"\n\n额外要求:\n{extra.strip()}" if extra else ""


def build_generate_messages(
    project: Project,
    chapter: Chapter,
    previous: list[Chapter],
    *,
    target_word_count: int = 3000,
    extra_instruction: str | None = None,
    characters: list[Character] | None = None,
    recent_events: list[PlotEvent] | None = None,
    world_entities: list[WorldEntity] | None = None,
    items: list[Item] | None = None,
    snapshots_by_id: dict[int, dict] | None = None,
    active_tasks: list[Task] | None = None,
    plot_threads: list[PlotThread] | None = None,
    db=None,
) -> list[dict]:
    char_names = {c.id: c.name for c in (characters or [])}
    values = {
        "project_info": _project_context(project),
        "synopsis_block": _synopsis_context(project),
        "threads_block": _threads_context(plot_threads or []),
        "previous_summary": _previous_chapters_context(previous, chapter.id),
        "characters_block": _characters_context(characters or [], snapshots_by_id),
        "world_block": _world_context(world_entities or []),
        "items_block": _items_context(items or []),
        "events_block": _recent_events_context(recent_events or [], previous),
        "tasks_block": _tasks_context(active_tasks or [], char_names),
        "beats_block": _beats_context(chapter.beats, target_word_count),
        "chapter_label": _chapter_label(chapter),
        "target_word_count": str(target_word_count),
        "extra_instruction_block": _extra_instruction_block(extra_instruction),
    }
    return prompt_service.render(db, "chapter.generate", values)


def build_continue_messages(
    project: Project,
    chapter: Chapter,
    previous: list[Chapter],
    *,
    cursor_text: str,
    extra_instruction: str | None = None,
    characters: list[Character] | None = None,
    recent_events: list[PlotEvent] | None = None,
    world_entities: list[WorldEntity] | None = None,
    items: list[Item] | None = None,
    snapshots_by_id: dict[int, dict] | None = None,
    active_tasks: list[Task] | None = None,
    plot_threads: list[PlotThread] | None = None,
    db=None,
) -> list[dict]:
    char_names = {c.id: c.name for c in (characters or [])}
    values = {
        "project_info": _project_context(project),
        "synopsis_block": _synopsis_context(project),
        "threads_block": _threads_context(plot_threads or []),
        "previous_summary": _previous_chapters_context(previous, chapter.id),
        "characters_block": _characters_context(characters or [], snapshots_by_id),
        "world_block": _world_context(world_entities or []),
        "items_block": _items_context(items or []),
        "events_block": _recent_events_context(recent_events or [], previous),
        "tasks_block": _tasks_context(active_tasks or [], char_names),
        "chapter_label": _chapter_label(chapter),
        "cursor_text": cursor_text,
        "extra_instruction_block": _extra_instruction_block(extra_instruction),
    }
    return prompt_service.render(db, "chapter.continue", values)


def build_rewrite_messages(
    *,
    selection: str,
    instruction: str,
    project: Project | None = None,
    characters: list[Character] | None = None,
    plot_threads: list[PlotThread] | None = None,
    db=None,
) -> list[dict]:
    project_info_block = (
        f"作品上下文:{_project_context(project)}" if project else ""
    )
    synopsis_block = _synopsis_context(project) if project else ""
    values = {
        "project_info_block": project_info_block,
        "synopsis_block": synopsis_block,
        "threads_block": _threads_context(plot_threads or []),
        "characters_block": _characters_context(characters or []),
        "instruction": instruction.strip(),
        "selection": selection,
    }
    return prompt_service.render(db, "chapter.rewrite", values)


def build_summarize_messages(chapter: Chapter, *, db=None) -> list[dict]:
    values = {
        "chapter_label": _chapter_label(chapter),
        "chapter_content": chapter.content or "",
    }
    return prompt_service.render(db, "chapter.summarize", values)


def build_suggest_beats_messages(
    project: Project,
    chapter: Chapter,
    previous: list[Chapter],
    *,
    target_word_count: int = 4000,
    extra_instruction: str | None = None,
    plot_threads: list[PlotThread] | None = None,
    db=None,
) -> list[dict]:
    values = {
        "project_info": _project_context(project),
        "synopsis_block": _synopsis_context(project),
        "threads_block": _threads_context(plot_threads or []),
        "previous_summary": _previous_chapters_context(previous, chapter.id),
        "chapter_label": _chapter_label(chapter),
        "chapter_summary": (chapter.summary or "").strip() or "(本章梗概暂未填)",
        "target_word_count": str(target_word_count),
        "extra_instruction_block": _extra_instruction_block(extra_instruction),
    }
    return prompt_service.render(db, "chapter.suggest_beats", values)


def build_score_messages(
    project: Project,
    chapter: Chapter,
    *,
    db=None,
) -> list[dict]:
    values = {
        "project_info": _project_context(project),
        "chapter_label": _chapter_label(chapter),
        "chapter_content": chapter.content or "",
    }
    return prompt_service.render(db, "chapter.score", values)


def build_style_check_messages(
    project: Project,
    chapter: Chapter,
    *,
    db=None,
) -> list[dict]:
    values = {
        "project_info": _project_context(project),
        "chapter_label": _chapter_label(chapter),
        "chapter_content": chapter.content or "",
    }
    return prompt_service.render(db, "chapter.style_check", values)
