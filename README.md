# AI Novel Writer

本地优先的 AI 辅助小说创作工具。把写作、人物档案、情节脉络、AI 生成统一在一个工作区里,数据存在本地 SQLite,API key 自带 — 完全可控。

## 特性

- **写作主线**:工程列表 / 章节管理 / Markdown 编辑器(CodeMirror 6)/ 1.5s 防抖自动保存
- **AI 生成**:整章生成 / 续写 / 改写选区 / 章节摘要,流式输出可预览可中断
- **人物档案**:手动维护 + AI 从已写章节自动抽取并合并
- **关系网络**:`A → 关系 → B` 卡片视图,AI 抽取
- **情节时间线**:按章节竖向排列的事件 + 重要度,带 AI 一致性检查
- **世界观维基**:地点 / 组织 / 物品 / 概念 4 类条目,AI 自动抽取,按类型分组浏览
- **进阶体系**:可挂多套阶梯(修仙/武道/魔功),按 genre 自动播种;玄幻类工程开箱即用
- **状态事件溯源**:记录境界突破/位置变化/获得失去物品/负伤,任意章节点的人物状态由事件回放得出
- **任务清单**:记录人物追求与未完成事项(寻师/复仇/夺物),状态/优先级/担当/起止章节
- **反向注入**:生成时勾选参与人物 + 世界观条目,自动叠加 [本章开始前快照] +
  [最近情节脉络] + [进行中任务] 塞进 prompt,AI 不会让金丹期人物突然弱化或丢物品
- **多 provider**:UI 切换 Claude / OpenAI / DeepSeek / 通义千问 / Ollama / 自定义,无需改代码
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
├── backend/      # FastAPI,87 个 pytest
├── frontend/     # Vue 3
├── data/         # 运行时数据(SQLite,不入 git)
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

候选:章节版本历史、章节分卷、时间线人物泳道可视化、生成结果对比 / 重生成。

## License

[MIT](LICENSE)
