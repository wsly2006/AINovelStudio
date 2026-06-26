# AI Novel Writer

本地优先的 AI 辅助小说创作工具。把写作、人物档案、情节脉络、AI 生成统一在一个工作区里,数据存在本地 SQLite,API key 自带 — 完全可控。

## 特性

- **写作主线**:工程列表 / 章节管理 / Markdown 编辑器(CodeMirror 6)/ 1.5s 防抖自动保存
- **大纲模式**:在「大纲」tab 一次性 AI 批量草拟连续 N 章的标题 / 梗概 / 节拍,
  落库为占位章节;再回「正文」tab 写。每章可单独编辑大纲,正文写完后可一键
  把正文与大纲对账,逐项给 covered / partial / missing
- **AI 生成**:整章生成 / 续写 / 改写选区 / 章节摘要,流式输出可预览可中断;
  编辑器内选中文字右键即可一键改写,工具栏按钮悬停有功能说明
- **章节评分**:AI 按文笔 / 情节 / 人物 / 综合 4 维打分,留历史曲线,列表显示最新分徽章
- **AI 文风检查**:挑出读起来「像 AI 写」的段落,给出原文片段、问题原因与重写方向,
  点「去改写」直接定位编辑器并预填改写指令
- **章节版本历史**:每次 AI 覆盖前自动快照,可手动打标签、对比 diff、单条还原 / 删除
- **审稿模型**:可在「模型配置」单独配一个模型专门跑评分 / 文风检查 / 一致性检查,
  避免「自评偏差」,也方便横向对比不同模型当评审的口味
- **人物档案**:手动维护 + AI 从已写章节自动抽取并合并
- **关系网络**:`A → 关系 → B` 卡片视图,AI 抽取
- **情节时间线**:按章节竖向排列的事件 + 重要度,带 AI 一致性检查
- **总纲 & 主线**:工程级长篇构思 + 多条主线(规划/进行/完结/弃置 4 状态、重要度、规划弧线),
  AI 一键抽线;事件可绑主线,planning→active 自动提升
- **章节节拍 + 对账**:写前列 3-5 个节拍引导生成,写后逐节拍 AI 判定 covered/partial/missing,
  差距一目了然
- **一致性问题状态**:`/plot/check` 结果按 run_id 分批持久化,可标记 open/resolved/dismissed
  跨次跟踪
- **AI prompt 预览**:生成前一键看到 system + user 完整内容,所见即所发
- **世界观维基**:地点 / 组织 / 物品 / 概念 4 类条目,AI 自动抽取,按类型分组浏览
- **进阶体系**:可挂多套阶梯(修仙/武道/魔功),按 genre 自动播种;玄幻类工程开箱即用
- **状态事件溯源**:记录境界突破/位置变化/获得失去物品/负伤,任意章节点的人物状态由事件回放得出
- **任务清单**:记录人物追求与未完成事项(寻师/复仇/夺物),状态/优先级/担当/起止章节
- **反向注入**:生成时勾选参与人物 + 世界观条目,自动叠加 [本章开始前快照] +
  [最近情节脉络] + [进行中任务] 塞进 prompt,AI 不会让金丹期人物突然弱化或丢物品
- **多 provider**:UI 切换 Claude / OpenAI / DeepSeek / 通义千问 / Ollama / 自定义,无需改代码
- **MCP 集成**:把工程数据通过 [Model Context Protocol](https://modelcontextprotocol.io)
  暴露出去,直接在 Claude Code / Claude Desktop / Cursor 里用自然语言查询和修改小说
  (默认只读;写操作需 env 开关显式启用,写章节正文前自动建版本快照可回滚)
- **数据自由**:JSON 完整备份(含人物 / 关系 / 情节 / 世界观 / 阶梯 / 状态事件 / 任务)
  + Markdown 阅读导出 / JSON 导入还原
- **多语言预埋**:文案集中在 i18n 包,目前提供中文,加新语种只需复制翻译

## 技术栈

- **后端**:Python 3.11+ / FastAPI / SQLAlchemy 2 / SQLite / LiteLLM
- **前端**:Vue 3 / Vite / Element Plus / CodeMirror 6 / Pinia / vue-i18n
- **包管理**:后端 [`uv`](https://github.com/astral-sh/uv),前端 npm

## 目录结构

```
AINovelWritor/
├── backend/      # FastAPI,246 个 pytest
├── frontend/     # Vue 3
├── data/         # 运行时数据(SQLite,不入 git)
├── docs/         # 本地设计文档(不入 git)
├── scripts/      # 一键启动脚本
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
# 后端(需要 uv)
cd backend && uv sync

# 前端(需要 Node 18+)
cd ../frontend && npm install
```

### 2. 配置 AI(可选,首次启动后也能在 UI 里改)

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env,放入任意一个 provider 的 API key
```

### 3. 启动

```bash
# Windows (Git Bash / WSL):
./scripts/start.sh

# Mac / Linux:
./scripts/start.sh
```

或分别启动:

```bash
# 终端 1:后端
cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8765

# 终端 2:前端
cd frontend && npm run dev
```

打开 http://localhost:5173 即可。

## AI Provider 配置

工作区右上角点「模型徽章」,选预设或自定义。各 provider 默认 model 名:

| Provider | model 示例 | 需要的环境变量 |
|---|---|---|
| Claude | `claude-opus-4-7` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| DeepSeek | `deepseek/deepseek-chat` | `DEEPSEEK_API_KEY` |
| 通义千问 | `dashscope/qwen-max` | `DASHSCOPE_API_KEY` |
| Moonshot Kimi | `moonshot/moonshot-v1-128k` | `MOONSHOT_API_KEY` |
| Gemini | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Ollama 本地 | `ollama/qwen2.5:14b` | 无需 key,起 `ollama serve` 即可 |

UI 里填的 key 加密保存方式:**直接明文存 SQLite**(本地单用户工具)。如果 `data/app.db` 会被分享出去,请改用 `.env` 注入,或不要在 UI 中保存 key。

LiteLLM 完整 provider 列表见 [docs.litellm.ai](https://docs.litellm.ai/docs/providers)。

## MCP 集成(在 Claude Code / Claude Desktop 里写小说)

仓库自带一个 MCP server,让任何兼容 MCP 的客户端(Claude Desktop、Claude Code
VS Code 插件、Cursor 等)直接读写本地的小说工程 — 共用同一份 `data/app.db`,
跟自家 UI 看到的是同一份数据。

**目前暴露 21 个工具**(读 18 + 写 3),覆盖工程 / 章节 / 人物 / 世界观 / 物品 /
情节事件 / 任务 / 关系 / 章节版本回滚,以及一个把"本章下笔需要的全套上下文"
聚合成结构化数据的 `get_writing_context`。

### 启动

MCP server 与 FastAPI 后端是独立进程,由 MCP 客户端按需拉起,**不需要手工启动**。
本地自检可以这样验证:

```bash
cd backend
uv sync                                 # 装依赖,首次需要
uv run python -m app.mcp.server         # 卡住等输入是正常的(stdio 协议),Ctrl+C 退出
```

要把写工具(`update_chapter` / `update_character` / `restore_chapter_version`)
也暴露给客户端,启动前显式打开开关(默认关闭):

```bash
# Bash / Zsh
export AI_NOVEL_MCP_ENABLE_WRITES=true

# PowerShell
$env:AI_NOVEL_MCP_ENABLE_WRITES = "true"
```

### Claude Code (VS Code) 配置

```bash
claude mcp add ai-novel \
  --command "uv" \
  --args "run" "python" "-m" "app.mcp.server" \
  --cwd "<this repo>/backend"
```

或编辑 `~/.claude.json` 的 `mcpServers` 段:

```json
{
  "mcpServers": {
    "ai-novel": {
      "command": "uv",
      "args": ["run", "python", "-m", "app.mcp.server"],
      "cwd": "<this repo>/backend"
    }
  }
}
```

启用写工具时再加一段 env:

```json
{
  "mcpServers": {
    "ai-novel": {
      "command": "uv",
      "args": ["run", "python", "-m", "app.mcp.server"],
      "cwd": "<this repo>/backend",
      "env": { "AI_NOVEL_MCP_ENABLE_WRITES": "true" }
    }
  }
}
```

重启 VS Code,`/mcp` 面板能看到 `ai-novel` 状态为 `connected`,工具列表里就是
本仓库暴露的所有读/写工具。

### Claude Desktop 配置

配置文件位置:

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

格式与 `~/.claude.json` 的 `mcpServers` 段完全一致(见上)。

### 用法示例

```
你: 我有哪些小说工程?
   → Claude 调 list_projects()

你: 给我看《修仙传》第一章写了啥
   → list_chapters → get_chapter

你: 把第一章标题改成「初入凡尘」
   → list_projects → list_chapters → update_chapter
   (需要先开 AI_NOVEL_MCP_ENABLE_WRITES=true)

你: 按现有设定续写第三章后半段
   → list_chapters → get_writing_context(拿人物快照/最近情节/任务)
   → Claude 自己写正文 → update_chapter(content=...)
   (改前自动建 chapter_versions 快照,可回滚)

你: 刚改的不喜欢,回到改之前
   → list_chapter_versions → restore_chapter_version
```

### 注意点

- **stdio 协议占用 stdout**,业务代码(包括你后续要加的工具)严禁 `print`,
  日志统一走 `logging`(默认 stderr)
- **Windows 路径**用正斜杠 `/` 或 `\\` 转义
- **冷启动 1-2 秒**(uv 初始化)— 客户端首次连接会等一下
- **写工具变更前会快照**:`update_chapter(content=...)` 会先把当前正文存进
  `chapter_versions` 再覆盖,最多保留最近 5 条 FIFO,可在 UI 或 MCP 里还原
- **Ollama 本地小模型** tool calling 经常翻车,推荐配 Claude / GPT / DeepSeek 等
  正经支持 function calling 的 provider 当 MCP 客户端

更详细的配置说明在 [`backend/app/mcp/README.md`](backend/app/mcp/README.md)。

## 开发约定

### 后端

```bash
cd backend
uv run pytest -v               # 运行测试
uv run ruff check app tests    # 检查
```

### 前端

```bash
cd frontend
npm run dev      # 开发
npm run build    # 生产构建
```

### 数据库迁移

首版用 `Base.metadata.create_all()` 启动建表,Schema 变化会自动建新表但**不会**改老表。如果你改了已有列,删 `data/app.db` 重新启动即可(开发期可接受;生产部署建议接 Alembic)。

## 数据安全

- 整个 `data/` 目录被 `.gitignore` 排除,工程数据不会泄露到仓库
- API key 不入仓库,`.env` 也在 `.gitignore` 里;UI 里填的 key 仅存在本机 `data/app.db`
- 所有 AI 调用直接走你配置的 provider,本工具不收集、不转发、不上报任何数据

## 路线图

已完成:

- Phase 1:首页 / 工程列表
- Phase 2:工作区 / 章节管理
- Phase 3:编辑器 + AI 生成(整章 / 续写 / 改写选区 / 摘要,SSE 流式可中断)
- Phase 4A:人物档案 + AI 抽取
- Phase 4B:关系图 + 情节时间线 + 一致性检查
- AI 反向注入(人物档案 + 最近情节脉络 + 世界观条目 + 本章开始前快照 + 进行中任务)
- 工程导入导出(JSON 完整备份 / Markdown 阅读导出)
- 模型配置 UI(预设 Claude / OpenAI / DeepSeek / 通义千问 / Kimi / Gemini / Ollama / 自定义)
- Phase 5:世界观维基(地点 / 组织 / 物品 / 概念)
- Phase 6:进阶体系(多套阶梯,按 genre 自动播种)+ 状态事件溯源 + 任务清单 + 时间线叠加人物变化轨迹
- Phase 7:章节版本历史(自动快照 + 手动打标签 + diff 对比 + 单条还原 / 删除)
- Phase 8:章节评分(4 维打分 + 历史趋势)+ AI 文风检查(挑 AI 味段落 + 一键定位改写)+ 双角色模型(写作 / 审稿独立配置)
- Phase 9:故事一致性流水线(总纲 → 主线 → 节拍 → 事件抽取 → 节拍-事件对账 → 一致性问题状态跟踪)+ AI prompt 预览
- Phase 10:MCP 集成(把全部领域数据 + 写章节工具通过 Model Context Protocol
  暴露给 Claude Code / Claude Desktop / Cursor;读默认开,写需 env 开关 +
  自动版本快照兜底)
- Phase 11:大纲模式(批量 AI 草拟连续 N 章的 title / summary / beats,
  落库为 outlined 占位章节;正文 tab 加章节-大纲对账,逐项 covered / partial / missing)

候选:章节分卷、时间线人物泳道可视化、生成结果对比 / 重生成、评分跨模型对比视图、
MCP 工具的章节全文搜索。

## License

[AGPL-3.0](LICENSE)

> 注意:AGPL-3.0 要求**网络服务**也要开源 — 如果你拿这个仓库改造后对外提供服务
> (SaaS / 公网部署 / 给客户托管),需要把你的修改同样以 AGPL-3.0 公开。本地自用、
> 公司内部使用、学习研究都不受影响。
