# 翻译 Pipeline（Translation Pipeline）设计方案

> 状态：已实现（M1-M6 合并到 main）
> 日期：2026-06-25
> 原始规划：todo/P0-translation-pipeline.md（已归档到本文档）

## 1. 背景与目标

### 用户场景

存量中文修仙/言情项目要做海外发行（KDP / Webnovel / 起点国际）。机翻一遍是不够的：

- **角色名一致性**：李慕白 → Li Mubai，整本 1000 章不能漂移
- **修真术语 / 黑话**：金丹、元婴、突破——海外读者完全无感
- **文化替换**：师父、拱手礼、龙凤意象——直译尴尬，过度西化丢味道
- **目标语文风**：Webnovel 英文短句多、对话密、cliffhanger 重，节奏跟中文不同

### 设计目标

- 把翻译当作一条可重复、可质检的「产线」，不是「一键翻译按钮」
- 数据层尽量复用现有模型（章节、版本系统）
- AI 调用集中在「术语抽取 + 章节翻译」两点，其余靠规则/字符串匹配
- 暴露 HTTP + MCP 两套入口，便于人工驱动也便于 LLM 编排

## 2. 数据模型决策

### 新增

| 表 / 字段 | 用途 |
|---|---|
| `translation_glossary` 表 | 项目级 (source, target_lang) 术语表 |
| `chapter_versions.lang` 字段 | 版本所属语种，默认 zh-CN |
| `projects.translation_style_guide` 字段 | 项目级风格指令（自然语言） |

### 关键决策

- **中文是唯一真相**：`chapter.content` 永远是中文，翻译只活在 `chapter_versions(lang=target_lang)` 里。非 zh-CN 版本禁止 restore 回 content。
- **版本 trim 按 (chapter_id, lang) 分桶**：每个语种独立保 5 条，互不挤压。
- **术语表唯一键 (project_id, source, target_lang)**：同一中文词在同一目标语只有一条译法。
- **不做文化替换 regex 表**（曾在 P0 原始 plan 中）：作者用风格指令自然语言写「师父译 Master」，AI 按语义处理，比 regex 引擎稳。

## 3. 实施里程碑

### M1 — 术语表 CRUD + 种子（commit `a59a044`）

- 表 + 路由 `/api/projects/{id}/glossary`、`/api/glossary/{id}`
- 「从已有数据导入」按钮：把 characters / items / world_entities 的 name + aliases 灌入术语表，target 留空
- `locked` 字段：作者校对锁定的条目永不被 seed/AI 覆盖
- 前端：术语表 tab、表格 + 过滤 + 内联锁

### M2 — AI 候选抽取（commit `488ac20`）

- SSE 路由 `POST /api/projects/{id}/glossary/extract`
- 逐章扫正文，AI 输出中文专有名词候选（entry_type 白名单兜底）
- 纯 merge：已存在的 source 跳过，target 留空交给 M3 翻译
- 前端：术语表页「AI 抽取」抽屉，按章进度

### M3 — 章节翻译核心（commit `7d763ac`）

- `chapter_versions` 加 `lang` 列 + 索引 `(chapter_id, lang, created_at)`
- Prompt `chapter.translate`：术语表全量注入 + 前序章节梗概
- SSE 路由 `POST /api/chapters/{id}/translate`，逐 token 流式
- 落库 `reason='translated', lang=target_lang`，5 条/语种独立 trim
- 前端：正文 tab AI 工具栏「翻译本章」按钮 + 翻译抽屉；版本历史按 lang 过滤 + 徽章

### M4 — 跨章一致性报告（commit `9753967`）

- 路由 `GET /api/projects/{id}/translation-consistency?target_lang=`
- 纯字符串匹配：每章最新译版若 source 在中文出现、target 不在译文 → 报一条 issue
- 只出报告不自动改：作者点 issue 跳到对应章手动重翻
- 前端：术语表页「一致性检查」按钮

### M5 — 翻译风格指令（commit `acf5ede`）

- `projects.translation_style_guide` TEXT 字段
- 翻译 prompt 增 `{{style_guide_block}}` 占位符，空时给兜底文案
- 前端：术语表页「风格指令」按钮，弹窗 8000 字 + 8 条可点击预设（Webnovel 短句风、师父译 Master、修真术语保留拼音 等）

### M6 — MCP tools（commit `549fc61`）

5 个工具暴露给 Claude Desktop / Code：

| 工具 | 危险等级 | 用途 |
|---|---|---|
| `list_glossary` | 读 | 查工程术语表 |
| `upsert_glossary_entry` | 写 | 创建或更新一条术语 |
| `translate_chapter` | 写 | 同步阻塞翻译一章 |
| `check_translation_consistency` | 读 | 跑一致性报告 |
| `get_chapter_version` | 读 | 拉完整译文 |

关键设计：`translate_chapter_blocking` 在 service 层用 `asyncio.run` 把异步 SSE 流收完，HTTP 路由仍走 generator 流式 —— 异步细节关在 service 里。

## 4. 服务层结构

```
backend/app/services/
  translation_glossary_service.py     # M1: CRUD + 种子
  glossary_extract_service.py         # M2: AI 抽取 SSE 生成器
  chapter_translation_service.py      # M3: 翻译 SSE + M6 blocking 包装
  translation_consistency_service.py  # M4: 字符串匹配报告
  chapter_version_service.py          # 共享:lang-aware snapshot / trim
```

## 5. API 一览

```
术语表
  GET    /api/projects/{id}/glossary?target_lang=&entry_type=
  POST   /api/projects/{id}/glossary
  POST   /api/projects/{id}/glossary/seed
  POST   /api/projects/{id}/glossary/extract           # SSE
  PATCH  /api/glossary/{id}
  DELETE /api/glossary/{id}

翻译
  POST   /api/chapters/{id}/translate                  # SSE
  GET    /api/chapters/{id}/versions?lang=             # 按语种过滤
  GET    /api/projects/{id}/translation-consistency?target_lang=

项目
  PATCH  /api/projects/{id}                            # 含 translation_style_guide
```

## 6. 测试覆盖

- 单元 + 集成共 287 个测试全绿
- 关键覆盖：
  - 术语表 CRUD + 冲突 + 种子（19 cases）
  - AI 抽取：dedup / invalid type 兜底 / 空章跳过 / SSE 流（4 cases）
  - 章节翻译：流式 + 落库 / 术语表注入 prompt / 按 lang 独立 trim / 译版禁止 restore（8 cases）
  - 一致性：missing target / 不在原文跳过 / 空 target 跳过 / 最新版本 / 404（6 cases）
  - MCP 工具：list / upsert / locked 跳过 / translate + preview 截断 / consistency / get_version / 注册自检（8 cases）

## 7. 已知未做项 / 后续

| 项 | 状态 | 去向 |
|---|---|---|
| 批量翻译队列 / 跨章串行执行 | 未做 | 挪到 [P6 工作项 4](../todo/P6-export-polish.md#工作项-4翻译批量队列) |
| 流式 token 进度（MCP 侧） | 未做 | MCP 同步语义不便，搁置 |
| 多目标语风格分桶 | 未做 | 当前一项目一份 guide，真要做改成 JSON dict |
| 文化替换 regex 引擎 | 取消 | 风格指令已覆盖，决定不做 |
| 译后回译质量评分 | 未做 | 太重，先靠人审 + 术语表覆盖率指标 |
| 西语 / 印尼语支持 | 已就位 | LANG_LABELS 已含 6 种语，prompt 共用，未实测 |

## 8. 验证标准（待跑）

P0 原始规划里写的端到端验证标准，工程层已就绪但**没真跑过**：

- 选一本现有完结的修仙短篇（10-20 章），跑完整 pipeline 输出英文版
- 标准：术语表 100% 覆盖 + 跨章名词零漂移
- 拿英文版给至少 1 个英文母语读者读前 3 章，能看懂、能继续读

这一步只能人工跑，不在工程范围内。

## 9. 相关文件指针

### 后端
- 模型：[backend/app/models/translation_glossary.py](../backend/app/models/translation_glossary.py)、[backend/app/models/chapter_version.py](../backend/app/models/chapter_version.py)（lang 字段）
- 服务：[backend/app/services/translation_glossary_service.py](../backend/app/services/translation_glossary_service.py)、[backend/app/services/glossary_extract_service.py](../backend/app/services/glossary_extract_service.py)、[backend/app/services/chapter_translation_service.py](../backend/app/services/chapter_translation_service.py)、[backend/app/services/translation_consistency_service.py](../backend/app/services/translation_consistency_service.py)
- Prompt：[backend/app/ai/prompt_registry.py](../backend/app/ai/prompt_registry.py) 中 `extract.glossary` / `chapter.translate`
- MCP：[backend/app/ai/tools/translation.py](../backend/app/ai/tools/translation.py)

### 前端
- 术语表页：[frontend/src/views/WorkspaceGlossary.vue](../frontend/src/views/WorkspaceGlossary.vue)
- 翻译抽屉：[frontend/src/components/ChapterTranslateDrawer.vue](../frontend/src/components/ChapterTranslateDrawer.vue)
- AI 抽取抽屉：[frontend/src/components/GlossaryExtractDrawer.vue](../frontend/src/components/GlossaryExtractDrawer.vue)
- 一致性报告：[frontend/src/components/ConsistencyReportDialog.vue](../frontend/src/components/ConsistencyReportDialog.vue)
- 风格指令：[frontend/src/components/TranslationStyleDialog.vue](../frontend/src/components/TranslationStyleDialog.vue)
- 版本历史（lang 过滤 + 徽章）：[frontend/src/components/ChapterHistoryDialog.vue](../frontend/src/components/ChapterHistoryDialog.vue)

### 测试
- [backend/tests/test_translation_glossary.py](../backend/tests/test_translation_glossary.py)
- [backend/tests/test_chapter_translation.py](../backend/tests/test_chapter_translation.py)
- [backend/tests/test_translation_consistency.py](../backend/tests/test_translation_consistency.py)
- [backend/tests/test_mcp_translation_tools.py](../backend/tests/test_mcp_translation_tools.py)
