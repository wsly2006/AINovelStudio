# P1 — 发布元数据 + 多格式导出（已完成）

> 完成于 2026-06-21，commit `5f45611`
> 后端 234 tests passed / 前端 vite build OK
> 状态：已上线，按需进入打磨阶段（见 [P6-export-polish.md](../P6-export-polish.md)）

## 它解决了什么问题

P1 之前，导出只产出 JSON 备份和 Markdown 阅读稿。这两种都不能直接上架任何平台：
- Amazon KDP 要 EPUB / docx + blurb + 7 keywords + 2 categories
- Webnovel / Royal Road / Wattpad 要按章 txt + 长简介 + 标签
- 起点 / 番茄 / 晋江要全本或分章 txt + 笔名 + 分类

P1 把"导出"从「打包成文件」升级为「打包成可上架的发布资产」。
用户在工作区填一次发布元数据，按目标平台一键产出符合该平台规范的产物 + 元数据副产物。

## 用户路径

```
工作区左导航「发布」  →  填笔名 / 系列 / blurb / 关键词 / 分类 / 目标平台
                                              ↓
工作区顶栏「导出」  →  选平台卡片  →  系统校验缺项  →  勾格式  →  浏览器下载
                                              ↓
                              文件 + metadata.json (+ kdp_listing.txt)
```

## 数据模型

### PlatformProfile（新表）

平台 = 推荐格式 + 必需元数据 + 章节策略 + 编码偏好 + 注意事项。
8 个预制 profile，启动时 seed，`is_preset=True` 防误删。

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | str, unique | `kdp` / `webnovel` / `royalroad` / `wattpad` / `qidian` / `fanqie` / `jjwxc` / `generic` |
| `name` | str | 显示名 |
| `region` | str | `global` / `cn` / `other`，UI 分组用 |
| `is_preset` | bool | 预制不可删 |
| `formats` | json | 该平台支持的格式列表，首项为推荐 |
| `chapter_strategy` | str | `whole_book` / `per_chapter` / `both` |
| `metadata_schema` | json | `[{key, label, required, type, max_len, max_count, hint}]`，仅作 UI 校验提示 |
| `encoding` | str? | txt 默认编码 `utf-8` / `gb18030` |
| `notes` | text? | 注意事项 markdown |

模型：[backend/app/models/platform_profile.py](../../backend/app/models/platform_profile.py)
服务：[backend/app/services/platform_profile_service.py](../../backend/app/services/platform_profile_service.py)

### Project 表扩字段

发布元数据存在 Project 上，平台 schema 仅做声明性约束（UI 校验）。
schema 改变只影响校验，不破坏数据。

```python
pen_name: str | None              # 笔名
series_name: str | None           # 系列名
series_index: int | None          # 第几本
blurb: str | None                 # 长简介（Amazon A+ / Webnovel synopsis）
keywords: list[str]               # 关键词
categories: list[str]             # 分类
target_platform_codes: list[str]  # 计划上的平台 code 列表
```

迁移：通过 `_apply_lightweight_migrations` 的 SQLite `ALTER TABLE ADD COLUMN` 补列；
新库由 `create_all` 直接建好。Export round-trip 同步带这些字段。

## 预制平台一览

| code | 名称 | region | formats | strategy | 必需元数据 |
|---|---|---|---|---|---|
| `kdp` | Amazon KDP | global | epub, docx | whole_book | pen_name, blurb, 7 keywords, 2 categories |
| `webnovel` | Webnovel | global | txt, txt_chapters, epub | both | pen_name, blurb, 2 genre |
| `royalroad` | Royal Road | global | txt, txt_chapters | per_chapter | pen_name, blurb, 8 tags |
| `wattpad` | Wattpad | global | txt, txt_chapters | per_chapter | pen_name, blurb, 1 category |
| `qidian` | 起点中文网 | cn | txt, txt_chapters | both | pen_name, blurb, 3 分类 |
| `fanqie` | 番茄小说 | cn | txt, txt_chapters | both | pen_name, blurb, 2 分类 |
| `jjwxc` | 晋江文学城 | cn | txt, txt_chapters | per_chapter | pen_name, blurb, 3 分类 |
| `generic` | 通用导出 | other | json, md, epub, docx, txt | both | 无强制 |

## API 端点

### 平台 profile
- `GET    /api/platforms` — 列出所有 profile（预制在前）
- `GET    /api/platforms/{id}` — 详情
- `POST   /api/platforms` — 用户自建
- `PATCH  /api/platforms/{id}` — 更新
- `DELETE /api/platforms/{id}` — 删除（预制返回 400）

路由：[backend/app/api/platforms.py](../../backend/app/api/platforms.py)

### 导出（原有保留 + 新增）
- `GET /api/projects/{id}/export.json` — 工程完整 JSON 备份
- `GET /api/projects/{id}/export.md` — Markdown 阅读稿
- `GET /api/projects/{id}/export.epub` — EPUB 3
- `GET /api/projects/{id}/export.docx` — Word docx
- `GET /api/projects/{id}/export.txt?mode=whole|chapters&encoding=utf-8|gb18030`
- `GET /api/projects/{id}/export.metadata.json` — 发布字段机器可读
- `GET /api/projects/{id}/export.kdp-listing.txt` — KDP 上架表单人工对照

路由：[backend/app/api/export.py](../../backend/app/api/export.py)

## 导出器分工

每个 exporter 是一个独立模块，无共享状态，便于单独测试和替换。

| 文件 | 职责 | 关键依赖 |
|---|---|---|
| [epub_exporter.py](../../backend/app/services/exporters/epub_exporter.py) | EPUB 3 生成，章节段落渲染，calibre:series 元数据 | `ebooklib>=0.18` |
| [docx_exporter.py](../../backend/app/services/exporters/docx_exporter.py) | Heading 1 章标题、分页符、首行缩进、core_properties | `python-docx>=1.1` |
| [txt_exporter.py](../../backend/app/services/exporters/txt_exporter.py) | 全本 `第 N 章` 格式 / 章节包 zip / UTF-8 ⟷ GB18030 编码切换 | 标准库 |
| [metadata_exporter.py](../../backend/app/services/exporters/metadata_exporter.py) | metadata.json + kdp_listing.txt 副产物 | 标准库 |

老的 [export_service.py](../../backend/app/services/export_service.py) 保留 JSON / Markdown，未拆出。
新格式都按 exporter-per-file 组织，避免一个文件膨胀到看不懂。

## 前端入口

### 发布元数据编辑页
[WorkspacePublish.vue](../../frontend/src/views/WorkspacePublish.vue)
- 左导航「发布」（Promotion 图标），路由 `workspace-publish`
- 四块卡片：笔名/系列、blurb、关键词 chips、分类 chips
- 目标平台多选（卡片网格，按 region 分组）
- 已选目标平台的最严上限驱动 UI 提示：
  - `keywords` 上限取所有目标平台 `max_count` 的最小值
  - `categories` 同理
  - `blurb` `max_len` 同理
- 超量红字告警；保存通过 `PATCH /api/projects/{id}`

### 导出弹窗
[ExportDialog.vue](../../frontend/src/components/ExportDialog.vue)
- 平台卡片网格（国内 / 海外 / 通用三组，单选高亮）
- 选平台后联动：
  - 默认勾上推荐格式（formats 数组首项）
  - 默认 encoding 取该 platform.encoding
  - 默认显示「附带元数据副产物」（选 KDP 时自动附加 kdp_listing.txt）
- 必需字段缺项 → 红色「缺少: xxx」+「去填写」跳转 `workspace-publish`
- 已填字段显示当前值预览
- 平台 `notes` 在折叠面板里
- 多格式串行 `<a>.click()` 间隔 250ms 触发下载（避免浏览器拦截）

工作区接入：[WorkspaceView.vue](../../frontend/src/views/WorkspaceView.vue) 顶栏「导出」按钮替换原 dropdown。

## 关键设计决策

### 1. 不建 PenName 全局表
本期需求是「每本书绑定笔名」，Project 上一个字符串字段够用。
当出现「按笔名筛选项目列表」「同一笔名跨平台账号统一管理」这类需求时再升级到外键。
迁移路径平滑：把字符串拆出独立表 + 外键替换。

### 2. metadata_schema 是声明，不是约束
schema 只用于 UI 校验提示，不约束 Project 表结构。
平台升级 metadata_schema 后旧工程数据不破，仅 UI 提示变化。
代价是：schema 与代码（导出器特化逻辑）之间一致性靠人工维护，目前 8 个平台规模可控。

### 3. EPUB 不嵌字体
依赖阅读器系统字体。Apple Books / Calibre / Webnovel 客户端都正常，
Kindle 设备读中文有概率字体丢失。若真有用户反馈再加可选 NotoSansCJK 子集（已记到 P6）。

### 4. GB18030 老编码兜底
起点等老平台仍要求 GB18030。不可表示字符用 `errors='replace'` 兜底并 `warning` 日志，
不直接抛错——多数情况下罕见字符替换比导出失败更可接受。

### 5. 章节策略 `both` 由 UI 决定
后端 exporter 提供 `mode=whole|chapters` 参数，前端按当前平台默认值预选，
不试图自动二选一——平台策略可能因连载阶段（前期整本 / 后期分章）变化。

### 6. 多文件下载用串行 a.click，不打 zip
当时选了简单方案：250ms 间隔串行触发原生下载。
缺点：视觉不优雅、严格浏览器策略下可能拦截。
打 zip 是已知优化项，已记到 [P6](../P6-export-polish.md)。

### 7. KDP listing 硬编码而非 schema-driven
metadata_exporter 只为 KDP 实现了 listing.txt，按其后台表单字段顺序硬编码排版。
更通用的「按 platform.metadata_schema 自动生成各平台 listing」是好抽象，
但目前 KDP 是唯一海外重要平台，单独覆盖已 unblock 主用例。其他平台的 listing 已记到 P6。

## 测试覆盖

| 文件 | 用例数 | 覆盖范围 |
|---|---|---|
| [test_platforms.py](../../backend/tests/test_platforms.py) | 5 | 预制 seed / 用户自建 / 预制不可删 / Project 元数据 round-trip |
| [test_export_epub.py](../../backend/tests/test_export_epub.py) | 2 | zip magic / mimetype / OPF 含 pen_name & blurb & keywords & calibre:series |
| [test_export_docx.py](../../backend/tests/test_export_docx.py) | 2 | document.xml 章节标题 / core.xml 元数据 |
| [test_export_txt.py](../../backend/tests/test_export_txt.py) | 5 | UTF-8 / GB18030 / 全本 / 章节包 zip / 错误参数 |
| [test_export_metadata.py](../../backend/tests/test_export_metadata.py) | 3 | metadata.json 字段 / KDP listing 超量提示 / 404 |

合计 17 个新用例，加入 backend 全套 234 tests 全绿。

## 后续衔接

- **P0 翻译完成后**：导出加「语言版本」维度，Project 复制英文版同样走这套链路
- **多笔名升级**：pen_name 字段平滑迁移到 PenName 外键
- **AI 辅助生成 blurb / keywords**：复用现有 LLM 栈，独立 PR，不打扰导出链路
- **P6 打磨**：合并 zip 下载 / 可选嵌入中文字体 / schema-driven 多平台 listing

## 相关代码路径

```
backend/app/
├── models/platform_profile.py        新表
├── models/project.py                 加 7 个发布字段
├── schemas/platform_profile.py       Pydantic schema
├── schemas/project.py                加 7 个发布字段
├── api/platforms.py                  新路由
├── api/export.py                     +6 个导出端点
├── services/platform_profile_service.py  CRUD + seed_presets
├── services/export_service.py        round-trip 带新字段
└── services/exporters/
    ├── __init__.py
    ├── epub_exporter.py
    ├── docx_exporter.py
    ├── txt_exporter.py
    └── metadata_exporter.py

frontend/src/
├── api/platforms.js                  axios 客户端
├── components/ExportDialog.vue       新弹窗
├── components/WorkspaceLeftNav.vue   加发布入口
├── views/WorkspacePublish.vue        新视图
├── views/WorkspaceView.vue           顶栏接入 ExportDialog
├── router/index.js                   workspace-publish 路由
└── i18n/locales/zh-CN.js             加 workspaceTab.publish
```
