"""提示词注册表:10 个内置 prompt 的默认模板 + 元数据。

设计:
- 每个 prompt 暴露若干 {{placeholder}},运行时由调用方填好块文本再渲染。
- 块文本本身仍然由 prompts.py / 各 extract service 的 _xxx_context 函数生成,
  这样模板里只是几个占位符,用户改起来不容易破坏内部逻辑。
- 用户改过的模板存 DB(prompt_templates),没改的回落这里的 default。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptDef:
    key: str
    name: str
    group: str  # writing / extract / analysis / outline
    description: str
    default_system: str
    default_user: str
    placeholders: tuple[str, ...]


# ============ 写作四件套共用的 system ============

_WRITING_SYSTEM = (
    "你是一名专业的中文小说写作助手。请用流畅自然的中文创作,"
    "保持人物形象与情节连贯一致,文笔贴合作品类型。"
    "段落之间只用单个换行符分隔,不要插入空行,不要使用双换行。"
    "输出仅包含正文,不要带 Markdown 代码块标记或任何解释性文字。"
)

# ============ 1. 章节生成 ============

_GEN_USER = """工程信息:{{project_info}}

前序章节梗概:
{{previous_summary}}

{{characters_block}}

{{world_block}}

{{items_block}}

{{events_block}}

{{tasks_block}}

现在请创作{{chapter_label}}。
目标字数:约 {{target_word_count}} 字。
请承接上一章结尾,自然推进情节。{{extra_instruction_block}}"""

# ============ 2. 续写 ============

_CONT_USER = """工程信息:{{project_info}}

前序章节梗概:
{{previous_summary}}

{{characters_block}}

{{world_block}}

{{items_block}}

{{events_block}}

{{tasks_block}}

当前正在写{{chapter_label}},已写到下面的位置,请从此处自然续写若干段。

已写内容:
---
{{cursor_text}}
---

请直接输出续写的部分,不要重复已写内容。{{extra_instruction_block}}"""

# ============ 3. 改写选段 ============

_REWRITE_USER = """{{project_info_block}}

{{characters_block}}

请按以下要求改写下面这段文字。

改写要求:{{instruction}}

原文:
---
{{selection}}
---

只输出改写后的文字。"""

# ============ 4. 章节梗概 ============

_SUMMARIZE_SYSTEM = "你是文本摘要助手,输出准确、客观、紧凑的中文梗概。"

_SUMMARIZE_USER = """请为以下章节生成一段简洁的梗概(80~150 字),概括关键事件、人物动向与情绪基调。只输出梗概本身。

章节标题:{{chapter_label}}

正文:
---
{{chapter_content}}
---"""

# ============ 5. 大纲建议(创建工程时) ============

_OUTLINE_SYSTEM = "你是一位经验丰富的网络小说大纲编辑,擅长长篇结构安排。"

_OUTLINE_USER = """你是网络小说的资深大纲编辑,请基于以下设定生成整本书的章节大纲。
{{outline_meta}}

输出格式严格遵循 JSONL,每行一个章节对象,顺序即章节顺序:
{"title": "副标题", "summary": "本章 60-180 字的概要"}

要求:
- title 只写副标题,不要带「第 N 章」前缀,8 字以内,可以为空字符串
- summary 必须写清本章发生的关键事件、人物动机、推进的冲突或伏笔
- 整本书要有起承转合:开篇钩子 → 立人设建世界 → 多次小冲突铺垫 → 中段反转 → 终章收束
- 严禁在 JSONL 之外输出任何说明、解释或 Markdown 代码块
- 必须输出恰好 {{chapter_count}} 行,不能多也不能少"""

# ============ 5b. AI 起书名 ============

_TITLE_SYSTEM = (
    "你是网络小说编辑兼营销,擅长为小说起既贴合内容又有钩子感的中文书名。"
    "输出严格遵循要求,禁止额外说明或代码块。"
)

_TITLE_USER = """请为下面这本小说生成 5 个候选书名。

设定信息:
{{outline_meta}}

要求:
- 每个书名 2~12 个汉字,简洁有力,避免空洞口号
- 风格贴合所给频道 / 题材 / 标签,5 个候选之间风格略有差异,不要全是同一种套路
- 不要带书名号《》、不要带副标题、不要带「之/与」连接的长串
- 严禁输出解释、点评或编号说明

输出格式:每行一个书名,共 5 行,仅书名本身。"""

# ============ 5c. AI 生简介 ============

_DESC_SYSTEM = (
    "你是网络小说编辑,擅长写打动人的中文小说简介(俗称「内容介绍」或「简介」)。"
    "输出严格遵循要求,禁止额外说明或代码块。"
)

_DESC_USER = """请为下面这本小说写一段中文简介。

设定信息:
{{outline_meta}}

要求:
- 80~150 字,一段成文,不分段、不分点、不要标题
- 必须交代主角身份、起点处境、核心冲突或目标,给读者一个想往下读的钩子
- 与所给频道 / 题材 / 标签匹配,避免空话套话
- 不要带书名号、不要「本书讲述」之类的元叙述
- 严禁输出解释或前后缀文字,仅输出简介正文。"""

# ============ 6. 人物抽取 ============

_EXTRACT_CHAR_SYSTEM = (
    "你是结构化信息抽取助手。从中文小说章节中提取人物信息,"
    "严格按要求输出 JSON,禁止额外解释或代码块标记。"
)

_EXTRACT_CHAR_USER = """已知人物列表(用于去重,新发现的人物请用其他名字):
{{existing_characters}}

章节:{{chapter_label}}

正文:
---
{{chapter_content}}
---

请输出 JSON,结构如下(若本章无新人物,也输出 {"characters": []}):
{
  "characters": [
    {
      "name": "人物主名(中文)",
      "aliases": ["别名1", "别名2"],
      "role": "主角/配角/反派/路人 之一",
      "profile": "一句话总览(20-60 字)",
      "appearance": "外貌描写(本章可见信息,无则留空)",
      "personality": "性格特征(本章可见信息,无则留空)",
      "background": "背景/经历(本章可见信息,无则留空)"
    }
  ]
}"""

# ============ 7. 世界观抽取 ============

_EXTRACT_WORLD_SYSTEM = (
    "你是结构化信息抽取助手。从中文小说章节中识别世界观元素(地点、组织、"
    "关键概念),严格输出 JSON。禁止额外解释或代码块标记。"
)

_EXTRACT_WORLD_USER = """本次需要抽取以下类别:

{{kind_blocks}}

章节:{{chapter_label}}

正文:
---
{{chapter_content}}
---

请输出 JSON。结构如下(若本章无新内容,也输出 {"entities": []}):
{
  "entities": [
    {
      "kind": "location|organization|concept",
      "name": "主名(中文)",
      "aliases": ["别名1"],
      "summary": "一句话总览(20-40 字)",
      "description": "详细说明(本章可见信息,无则留空)",
      "tags": ["标签1"]
    }
  ]
}"""

# ============ 7b. 物品抽取 ============

_EXTRACT_ITEMS_SYSTEM = (
    "你是结构化信息抽取助手。从中文小说章节中识别值得入库的物品"
    "(法宝 / 神兵 / 重要道具 / 灵药 / 信物 等),严格输出 JSON。"
    "禁止额外解释或代码块标记。"
)

_EXTRACT_ITEMS_USER = """已知物品列表(用于去重,新发现的请用其他名字):
{{existing_items}}

章节:{{chapter_label}}

正文:
---
{{chapter_content}}
---

只抽取在剧情中有具体功能 / 来历 / 名字的物品,日常用品(水、衣服、桌椅等)不抽。
请输出 JSON。结构如下(若本章无新内容,也输出 {"items": []}):
{
  "items": [
    {
      "name": "主名(中文)",
      "aliases": ["别名1"],
      "summary": "一句话总览(20-40 字)",
      "description": "详细说明(本章可见信息,无则留空)",
      "tags": ["标签1"]
    }
  ]
}"""

# ============ 8. 关系抽取 ============

_EXTRACT_REL_SYSTEM = (
    "你是结构化信息抽取助手。从中文小说章节中识别人物关系,严格输出 JSON。"
    "禁止额外解释或代码块标记。"
)

_EXTRACT_REL_USER = """已知人物列表(只能在这些人物间建立关系):
{{characters_brief}}

章节:{{chapter_label}}

正文:
---
{{chapter_content}}
---

请基于本章正文识别人物之间的关系(已存在的关系也可重复列出),输出 JSON:
{
  "relations": [
    {"from_id": 1, "to_id": 2, "type": "父子/师徒/恋人/朋友/敌对/...",
     "description": "本章中此关系的具体表现(20-60 字)"}
  ]
}"""

# ============ 9. 情节抽取 ============

_EXTRACT_PLOT_SYSTEM = (
    "你是情节摘要助手。把章节切分为若干关键事件,严格输出 JSON。"
    "禁止额外解释或代码块标记。"
)

_EXTRACT_PLOT_USER = """已知人物列表(用 id 引用):
{{characters_brief}}

章节:{{chapter_label}}

正文:
---
{{chapter_content}}
---

请把本章拆为 2~6 个关键事件,按出现顺序排列。输出 JSON:
{
  "events": [
    {
      "title": "事件标题(15 字以内)",
      "description": "事件描述(40-100 字)",
      "character_ids": [1, 2],
      "importance": 3
    }
  ]
}"""

# ============ 10. 情节自检 ============

_CHECK_SYSTEM = (
    "你是小说编辑助手。检查给定的人物档案与情节事件之间是否存在矛盾或缺漏,"
    "严格输出 JSON。禁止额外解释或代码块标记。"
)

_CHECK_USER = """工程:《{{project_name}}》

人物档案:
{{characters_brief}}

情节事件(按章节顺序):
{{events_brief}}

请找出潜在问题,例如:人物前后描写矛盾、情节逻辑断裂、伏笔未收、人物突然消失或登场未交代、关系冲突等。如无问题,issues 返回空数组。
输出 JSON:
{
  "issues": [
    {"kind": "矛盾/逻辑断裂/伏笔未收/人物缺失/...",
     "title": "问题概括(20 字内)",
     "detail": "具体说明(50-150 字)",
     "related_event_ids": [1, 2],
     "related_character_ids": [3]}
  ]
}"""


PROMPTS: tuple[PromptDef, ...] = (
    PromptDef(
        key="chapter.generate",
        name="生成新章节",
        group="writing",
        description="编辑器「AI 生成」整章正文时使用。",
        default_system=_WRITING_SYSTEM,
        default_user=_GEN_USER,
        placeholders=(
            "project_info", "previous_summary", "characters_block", "world_block",
            "items_block", "events_block", "tasks_block", "chapter_label",
            "target_word_count", "extra_instruction_block",
        ),
    ),
    PromptDef(
        key="chapter.continue",
        name="续写",
        group="writing",
        description="编辑器「续写」从光标处接着写。",
        default_system=_WRITING_SYSTEM,
        default_user=_CONT_USER,
        placeholders=(
            "project_info", "previous_summary", "characters_block", "world_block",
            "items_block", "events_block", "tasks_block", "chapter_label",
            "cursor_text", "extra_instruction_block",
        ),
    ),
    PromptDef(
        key="chapter.rewrite",
        name="改写选段",
        group="writing",
        description="编辑器右键「改写」选中文字。",
        default_system=_WRITING_SYSTEM,
        default_user=_REWRITE_USER,
        placeholders=("project_info_block", "characters_block", "instruction", "selection"),
    ),
    PromptDef(
        key="chapter.summarize",
        name="章节梗概",
        group="writing",
        description="给单章生成 80~150 字摘要。",
        default_system=_SUMMARIZE_SYSTEM,
        default_user=_SUMMARIZE_USER,
        placeholders=("chapter_label", "chapter_content"),
    ),
    PromptDef(
        key="project.outline",
        name="工程大纲建议",
        group="outline",
        description="新建工程时按设定生成整本书的章节大纲(JSONL 流)。",
        default_system=_OUTLINE_SYSTEM,
        default_user=_OUTLINE_USER,
        placeholders=("outline_meta", "chapter_count"),
    ),
    PromptDef(
        key="project.suggest_title",
        name="AI 起书名",
        group="outline",
        description="新建工程时按已填的题材 / 标签 / 简介生成 5 个候选书名。",
        default_system=_TITLE_SYSTEM,
        default_user=_TITLE_USER,
        placeholders=("outline_meta",),
    ),
    PromptDef(
        key="project.suggest_description",
        name="AI 生简介",
        group="outline",
        description="新建工程时按已填的书名 / 题材 / 标签生成 80~150 字简介。",
        default_system=_DESC_SYSTEM,
        default_user=_DESC_USER,
        placeholders=("outline_meta",),
    ),
    PromptDef(
        key="extract.character",
        name="人物抽取",
        group="extract",
        description="从章节正文识别新人物并入库。",
        default_system=_EXTRACT_CHAR_SYSTEM,
        default_user=_EXTRACT_CHAR_USER,
        placeholders=("existing_characters", "chapter_label", "chapter_content"),
    ),
    PromptDef(
        key="extract.world",
        name="世界观抽取",
        group="extract",
        description="从章节正文识别地点 / 组织 / 概念。",
        default_system=_EXTRACT_WORLD_SYSTEM,
        default_user=_EXTRACT_WORLD_USER,
        placeholders=("kind_blocks", "chapter_label", "chapter_content"),
    ),
    PromptDef(
        key="extract.items",
        name="物品抽取",
        group="extract",
        description="从章节正文识别有名物品(法宝 / 神兵 / 道具 等)。",
        default_system=_EXTRACT_ITEMS_SYSTEM,
        default_user=_EXTRACT_ITEMS_USER,
        placeholders=("existing_items", "chapter_label", "chapter_content"),
    ),
    PromptDef(
        key="extract.relation",
        name="关系抽取",
        group="extract",
        description="从章节正文识别人物间关系。",
        default_system=_EXTRACT_REL_SYSTEM,
        default_user=_EXTRACT_REL_USER,
        placeholders=("characters_brief", "chapter_label", "chapter_content"),
    ),
    PromptDef(
        key="extract.plot",
        name="情节抽取",
        group="analysis",
        description="把章节切分成 2~6 个关键事件。",
        default_system=_EXTRACT_PLOT_SYSTEM,
        default_user=_EXTRACT_PLOT_USER,
        placeholders=("characters_brief", "chapter_label", "chapter_content"),
    ),
    PromptDef(
        key="analysis.check",
        name="情节一致性检查",
        group="analysis",
        description="基于人物 + 情节事件,找潜在矛盾 / 伏笔未收 / 人物缺失。",
        default_system=_CHECK_SYSTEM,
        default_user=_CHECK_USER,
        placeholders=("project_name", "characters_brief", "events_brief"),
    ),
)


_BY_KEY: dict[str, PromptDef] = {p.key: p for p in PROMPTS}


def all_prompts() -> tuple[PromptDef, ...]:
    return PROMPTS


def get(key: str) -> PromptDef:
    if key not in _BY_KEY:
        raise KeyError(f"未知的 prompt key: {key}")
    return _BY_KEY[key]
