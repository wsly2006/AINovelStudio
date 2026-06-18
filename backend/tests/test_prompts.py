"""Prompt 反向注入测试。

直接调 prompts 模块,不依赖 LLM。
"""

from app.ai import prompts
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.plot_event import PlotEvent
from app.models.project import Project
from app.models.world_entity import WorldEntity


def _project() -> Project:
    p = Project(id=1, name="测试", genre="玄幻", description="少年剑客成长")
    return p


def _chapter(id_: int, order: int, title: str, summary: str | None = None) -> Chapter:
    c = Chapter(
        id=id_,
        project_id=1,
        title=title,
        order_index=order,
        content="",
        summary=summary,
        word_count=0,
        status="draft",
    )
    return c


def _character(id_: int, name: str, **extra) -> Character:
    return Character(id=id_, project_id=1, name=name, aliases=extra.get("aliases", []), **{
        k: v for k, v in extra.items() if k != "aliases"
    })


def _event(id_: int, chapter_id: int, title: str, desc: str = "") -> PlotEvent:
    return PlotEvent(
        id=id_,
        project_id=1,
        chapter_id=chapter_id,
        title=title,
        description=desc,
        character_ids=[],
        importance=3,
        order_in_chapter=1,
    )


def test_generate_without_injection() -> None:
    p = _project()
    chapters = [_chapter(1, 1, "序章", summary="主角出场"), _chapter(2, 2, "下山")]
    msgs = prompts.build_generate_messages(p, chapters[1], chapters)
    user = msgs[1]["content"]
    assert "《测试》" in user
    assert "序章" in user
    assert "目标字数" in user
    # 无人物档案块
    assert "参与人物档案" not in user
    assert "情节脉络" not in user


def test_generate_with_characters() -> None:
    p = _project()
    chapters = [_chapter(1, 1, "序章", summary="..."), _chapter(2, 2, "下山")]
    chars = [
        _character(
            1, "李小白",
            aliases=["小白哥"],
            role="主角",
            profile="十八岁少年剑客",
            personality="桀骜",
        ),
        _character(2, "张师傅", role="配角", background="隐世高人"),
    ]
    msgs = prompts.build_generate_messages(p, chapters[1], chapters, characters=chars)
    user = msgs[1]["content"]
    assert "参与人物档案" in user
    assert "李小白" in user
    assert "小白哥" in user
    assert "桀骜" in user
    assert "张师傅" in user
    assert "隐世高人" in user


def test_generate_with_events() -> None:
    p = _project()
    chapters = [_chapter(1, 1, "序章", summary="..."), _chapter(2, 2, "下山")]
    events = [
        _event(10, 1, "拜师", "李小白拜入山门"),
        _event(11, 1, "习剑", "苦练三年"),
    ]
    msgs = prompts.build_generate_messages(p, chapters[1], chapters, recent_events=events)
    user = msgs[1]["content"]
    assert "情节脉络" in user
    assert "拜师" in user
    assert "李小白拜入山门" in user
    assert "习剑" in user


def test_continue_with_injection() -> None:
    p = _project()
    chapters = [_chapter(1, 1, "序章", summary="..."), _chapter(2, 2, "下山")]
    chars = [_character(1, "李小白", role="主角")]
    msgs = prompts.build_continue_messages(
        p, chapters[1], chapters,
        cursor_text="他抬头望天",
        characters=chars,
    )
    user = msgs[1]["content"]
    assert "他抬头望天" in user
    assert "李小白" in user
    assert "请直接输出续写" in user


def test_rewrite_with_characters() -> None:
    p = _project()
    chars = [_character(1, "李小白", personality="冷静沉稳")]
    msgs = prompts.build_rewrite_messages(
        selection="他笑了笑。",
        instruction="改得更冷一些",
        project=p,
        characters=chars,
    )
    user = msgs[1]["content"]
    assert "他笑了笑。" in user
    assert "李小白" in user
    assert "冷静沉稳" in user


def test_extra_instruction_appears() -> None:
    p = _project()
    chapters = [_chapter(1, 1, "序章")]
    msgs = prompts.build_generate_messages(
        p, chapters[0], chapters,
        extra_instruction="结尾留悬念",
    )
    user = msgs[1]["content"]
    assert "结尾留悬念" in user


def test_generate_with_world_entities() -> None:
    p = _project()
    chapters = [_chapter(1, 1, "序章")]
    entities = [
        WorldEntity(id=1, project_id=1, kind="location", name="青云山",
                    aliases=["云山"], summary="终年积雪的主峰", tags=[]),
        WorldEntity(id=2, project_id=1, kind="organization", name="青云宗",
                    aliases=[], summary="正道魁首", tags=[]),
        WorldEntity(id=3, project_id=1, kind="concept", name="御剑术",
                    aliases=[], summary="正宗心法", tags=[]),
    ]
    msgs = prompts.build_generate_messages(
        p, chapters[0], chapters, world_entities=entities
    )
    user = msgs[1]["content"]
    assert "世界观设定" in user
    assert "青云山" in user
    assert "云山" in user  # 别名
    assert "青云宗" in user
    assert "御剑术" in user
    assert "终年积雪的主峰" in user
    # 按 kind 分组
    assert "【地点】" in user
    assert "【组织】" in user
    assert "【概念】" in user


def test_continue_with_world_entities() -> None:
    p = _project()
    chapters = [_chapter(1, 1, "序章")]
    entities = [WorldEntity(id=1, project_id=1, kind="concept", name="御风诀",
                             aliases=[], summary="顶级身法", tags=[])]
    msgs = prompts.build_continue_messages(
        p, chapters[0], chapters,
        cursor_text="他纵身一跃",
        world_entities=entities,
    )
    user = msgs[1]["content"]
    assert "御风诀" in user
    assert "他纵身一跃" in user
    assert "【概念】" in user


def test_no_world_when_empty() -> None:
    """缺省时不污染 prompt。"""
    p = _project()
    chapters = [_chapter(1, 1, "序章")]
    msgs = prompts.build_generate_messages(p, chapters[0], chapters)
    user = msgs[1]["content"]
    assert "世界观设定" not in user


def test_generate_with_snapshot_injection() -> None:
    """Phase 6.4 核心:snapshot 字段把"本章开始前"的状态注入。"""
    p = _project()
    chapters = [_chapter(1, 1, "序章"), _chapter(2, 2, "下山")]
    chars = [_character(1, "李逍遥", role="主角")]
    snapshots = {
        1: {
            "tier_label": "金丹期",
            "location_name": "青云山",
            "item_names": ["玄铁剑", "疗伤丹"],
            "injuries": ["左臂旧伤"],
        }
    }
    msgs = prompts.build_generate_messages(
        p, chapters[1], chapters,
        characters=chars,
        snapshots_by_id=snapshots,
    )
    user = msgs[1]["content"]
    assert "本章开始前状态" in user
    assert "金丹期" in user
    assert "青云山" in user
    assert "玄铁剑" in user
    assert "疗伤丹" in user
    assert "左臂旧伤" in user


def test_no_snapshot_when_not_provided() -> None:
    p = _project()
    chapters = [_chapter(1, 1, "序章")]
    chars = [_character(1, "李逍遥")]
    msgs = prompts.build_generate_messages(p, chapters[0], chapters, characters=chars)
    user = msgs[1]["content"]
    assert "本章开始前状态" not in user
