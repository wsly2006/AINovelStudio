# AI Novel Writer

[中文](README.md) | **English**

A local-first, AI-assisted novel writing tool. Writing, character profiles, plot threads, and AI generation all live in a single workspace. Data is stored in a local SQLite database, and you bring your own API keys — fully under your control.

## Features

- **Writing backbone**: project list / chapter management / Markdown editor (CodeMirror 6) / 1.5s debounced auto-save
- **Outline mode**: in the "Outline" tab, batch-draft titles / summaries / beats for N consecutive chapters with AI in one go, persisting them as placeholder chapters; then switch back to the "Body" tab to write. Each chapter's outline can be edited individually, and after the body is written you can one-click reconcile the body against the outline, marking each item covered / partial / missing
- **AI generation**: full-chapter generation / continue writing / rewrite selection / chapter summary, with streamable, previewable, interruptible output; select text in the editor and right-click to rewrite in one click; toolbar buttons show tooltips on hover
- **Chapter scoring**: AI scores across 4 dimensions — prose / plot / character / overall — keeps a historical trend, and the chapter list shows a badge with the latest score
- **AI style check**: picks out paragraphs that read "like AI wrote them", gives the original snippet, the reason, and a rewrite direction; click "Go rewrite" to jump straight into the editor with a pre-filled rewrite prompt; also ships 6 objective style signals (sentence-length variance / lexical richness / dialogue ratio / punctuation density, etc.) as informed reference
- **Author voice**: project-level verbal tics list + style description, automatically injected into the prompt on every AI generation / continuation / rewrite, so the output keeps your personal voice and isn't drowned out by generic AI style
- **Chapter version history**: auto-snapshot before every AI overwrite; supports manual tagging, diff comparison, and per-entry restore / delete
- **Reviewer model**: configure a separate model in "Model config" dedicated to running scoring / style check / consistency check, avoiding "self-evaluation bias" and making it easy to compare how different models perform as reviewers
- **Character profiles**: manually maintained + AI-extracted from written chapters and merged
- **Relationship network**: `A → relationship → B` card view, AI-extracted
- **Plot timeline**: chapter-stacked events + importance, with AI consistency check
- **Synopsis & main threads**: project-level long-form premise + multiple main threads (4 states: planned / active / completed / abandoned, plus importance and arc planning); AI one-click extraction; events can be bound to threads, auto-promoted planning→active
- **Chapter beats + reconciliation**: list 3-5 beats before writing to steer generation; after writing, AI judges each beat covered / partial / missing so gaps are clear at a glance
- **Consistency issue status**: `/plot/check` results are persisted in batches by run_id, markable as open / resolved / dismissed and tracked across runs
- **AI prompt preview**: one click to see the full system + user content before generation — what you see is what gets sent
- **Worldbuilding wiki**: 4 entry types — locations / organizations / items / concepts — AI-extracted and browsable grouped by type
- **Progression systems**: mount multiple ladders (cultivation / martial / magic), auto-seeded by genre; xianxia-style projects work out of the box
- **Stateful event sourcing**: records realm breakthroughs / location changes / item gains & losses / injuries; a character's state at any chapter is derived by replaying events
- **Task list**: tracks character goals and open items (find a master / revenge / seize an item), with status / priority / owner / start-end chapters
- **Reverse injection**: when generating, tick participating characters + worldbuilding entries to auto-stack [snapshot before this chapter] + [recent plot thread] + [in-progress tasks] into the prompt, so AI won't suddenly weaken a Golden Core-stage character or drop an item
- **Multi-provider**: switch Claude / OpenAI / DeepSeek / Qwen / Ollama / custom from the UI — no code changes
- **MCP integration**: exposes project data via the [Model Context Protocol](https://modelcontextprotocol.io), letting you query and edit the novel in natural language directly inside Claude Code / Claude Desktop / Cursor (read-only by default; write operations require an explicit env toggle, and a version snapshot is auto-created before any chapter body write so you can roll back)
- **Data freedom**: full JSON backup (including characters / relationships / plot / worldbuilding / ladders / stateful events / tasks) + Markdown reading export / JSON import to restore
- **Multi-language switcher**: one-click switch between Chinese / English in the top-right; the choice is persisted to localStorage; Element Plus built-in copy (dialogs, pagination, dates) follows the switch. Currently only Chinese has a full translation; English is a placeholder (missing keys fall back to Chinese). To add a language or fill in translations, see "Internationalization" below

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy 2 / SQLite / LiteLLM
- **Frontend**: Vue 3 / Vite / Element Plus / CodeMirror 6 / Pinia / vue-i18n
- **Package manager**: backend uses [`uv`](https://github.com/astral-sh/uv), frontend uses npm

## Directory Structure

```
AINovelWritor/
├── backend/      # FastAPI, 246 pytest tests
├── frontend/     # Vue 3
├── data/         # Runtime data (SQLite, not in git)
├── docs/         # Local design docs (not in git)
├── scripts/      # One-click launch scripts
└── README.md
```

## Quick Start

### 1. Install dependencies

```bash
# Backend (requires uv)
cd backend && uv sync

# Frontend (requires Node 18+)
cd ../frontend && npm install
```

### 2. Configure AI (optional; can also be changed in the UI after first launch)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and drop in any one provider's API key
```

### 3. Launch

Single window (recommended; Ctrl+C exits both):

```bash
# Mac / Linux / Git Bash / WSL
./scripts/run.sh                  # Defaults: backend=8765, frontend=5173
./scripts/run.sh 9000 5200        # Custom ports: 1st arg backend, 2nd arg frontend

# Windows native cmd
scripts\run.bat
scripts\run.bat 9000 5200
```

Or two windows (one terminal each for backend / frontend; closing the window stops it):

```bash
# Mac / Linux / Git Bash / WSL
./scripts/start.sh

# Windows native cmd
scripts\start.bat
```

Or start them separately:

```bash
# Terminal 1: backend
cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8765

# Terminal 2: frontend
cd frontend && npm run dev
```

Open http://localhost:5173 and you're in.

## AI Provider Configuration

Click the "model badge" in the top-right of the workspace and pick a preset or custom. Default model names per provider:

| Provider | model example | Required env var |
|---|---|---|
| Claude | `claude-opus-4-7` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| DeepSeek | `deepseek/deepseek-chat` | `DEEPSEEK_API_KEY` |
| Qwen (Tongyi) | `dashscope/qwen-max` | `DASHSCOPE_API_KEY` |
| Moonshot Kimi | `moonshot/moonshot-v1-128k` | `MOONSHOT_API_KEY` |
| Gemini | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Ollama (local) | `ollama/qwen2.5:14b` | No key needed; just run `ollama serve` |

How keys entered in the UI are stored: **as plaintext in SQLite** (this is a local single-user tool). If `data/app.db` will be shared, inject via `.env` instead, or don't save keys in the UI.

For the full LiteLLM provider list, see [docs.litellm.ai](https://docs.litellm.ai/docs/providers).

## MCP Integration (writing the novel inside Claude Code / Claude Desktop)

The repo ships an MCP server that lets any MCP-compatible client (Claude Desktop, the Claude Code VS Code extension, Cursor, etc.) read and write the local novel project directly — it shares the same `data/app.db`, so it's the exact same data the built-in UI shows.

**Currently exposes 21 tools** (18 read + 3 write), covering projects / chapters / characters / worldbuilding / items / plot events / tasks / relationships / chapter-version rollback, plus a `get_writing_context` that aggregates "the full context needed to draft this chapter" into structured data.

### Launching

The MCP server is a separate process from the FastAPI backend, spun up on demand by the MCP client — **no manual startup needed**. For a local self-check:

```bash
cd backend
uv sync                                 # Install deps, needed the first time
uv run python -m app.mcp.server         # Hanging waiting for input is normal (stdio protocol); Ctrl+C to exit
```

To also expose the write tools (`update_chapter` / `update_character` / `restore_chapter_version`) to clients, explicitly flip the switch before launch (off by default):

```bash
# Bash / Zsh
export AI_NOVEL_MCP_ENABLE_WRITES=true

# PowerShell
$env:AI_NOVEL_MCP_ENABLE_WRITES = "true"
```

### Claude Code (VS Code) configuration

```bash
claude mcp add ai-novel \
  --command "uv" \
  --args "run" "python" "-m" "app.mcp.server" \
  --cwd "<this repo>/backend"
```

Or edit the `mcpServers` section of `~/.claude.json`:

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

When enabling write tools, add an env block:

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

Restart VS Code; the `/mcp` panel should show `ai-novel` as `connected`, and the tool list will contain every read/write tool exposed by this repo.

### Claude Desktop configuration

Config file locations:

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

The format is identical to the `mcpServers` section of `~/.claude.json` (see above).

### Usage examples

```
You: What novel projects do I have?
   → Claude calls list_projects()

You: Show me what's written in Chapter 1 of "Cultivation Chronicles"
   → list_chapters → get_chapter

You: Rename Chapter 1 to "First Steps into the Mortal World"
   → list_projects → list_chapters → update_chapter
   (requires AI_NOVEL_MCP_ENABLE_WRITES=true first)

You: Continue the second half of Chapter 3 based on the existing setup
   → list_chapters → get_writing_context (gets character snapshot / recent plot / tasks)
   → Claude writes the body itself → update_chapter(content=...)
   (auto-creates a chapter_versions snapshot before overwriting, rollable back)

You: I don't like what I just changed, go back to before
   → list_chapter_versions → restore_chapter_version
```

### Caveats

- **The stdio protocol owns stdout**; business code (including any tools you add later) must never `print`. Logging goes through `logging` (stderr by default)
- **Windows paths**: use forward slashes `/` or escape with `\\`
- **1-2 second cold start** (uv initialization) — the client will wait a bit on first connect
- **Write tools snapshot before changes**: `update_chapter(content=...)` first stores the current body into `chapter_versions` before overwriting, keeping at most the latest 5 FIFO; restorable from the UI or MCP
- **Ollama local small models** frequently botch tool calling; recommend pairing with Claude / GPT / DeepSeek or another provider that properly supports function calling as the MCP client

More detailed configuration notes are in [`backend/app/mcp/README.md`](backend/app/mcp/README.md).

## Development Conventions

### Backend

```bash
cd backend
uv run pytest -v               # Run tests
uv run ruff check app tests    # Lint
```

### Frontend

```bash
cd frontend
npm run dev      # Development
npm run build    # Production build
```

### Database migrations

The first version uses `Base.metadata.create_all()` to create tables on startup; schema changes create new tables but **do not** alter existing ones. If you change an existing column, just delete `data/app.db` and restart (acceptable during development; for production deployment, consider wiring up Alembic).

### Internationalization

The frontend uses [vue-i18n](https://vue-i18n.intlify.dev/) for copy, with a built-in language switcher in the top-right. Registered locales live in `SUPPORTED_LOCALES` in [`frontend/src/i18n/index.js`](frontend/src/i18n/index.js).

**Layout:**

```
frontend/src/i18n/
├── index.js              # vue-i18n instance + setLocale() + localStorage persistence
└── locales/
    ├── zh-CN.js          # Chinese, full translation
    └── en-US.js          # English, currently a placeholder empty object; missing keys fall back to Chinese
```

**Translating English (or filling in an existing locale):**

Edit the corresponding `locales/xx-YY.js`, copy the keys from `zh-CN.js` and translate them one by one. Empty keys automatically fall back to `zh-CN`, so you can translate incrementally — no need to finish in one pass.

**Adding a new locale (e.g. Japanese `ja-JP`):**

1. `cp frontend/src/i18n/locales/en-US.js frontend/src/i18n/locales/ja-JP.js`, then translate item by item
2. In [`frontend/src/i18n/index.js`](frontend/src/i18n/index.js) `import` it, and add it to `messages` and `SUPPORTED_LOCALES`
3. In [`frontend/src/components/LocaleSwitcher.vue`](frontend/src/components/LocaleSwitcher.vue) add an entry to `LABELS`: `'ja-JP': '日本語'`
4. If Element Plus also has a matching locale, add a mapping in [`frontend/src/App.vue`](frontend/src/App.vue) (otherwise Element Plus dialogs / pagination copy won't follow)

**Language selection rules:**

- First visit: prefer `navigator.language`; `en*` goes to English, everything else to `zh-CN`
- After that: when the user switches in the top-right, it's stored in `localStorage['ai-novel-locale']` and read directly next time

**Using copy in page components:**

```vue
<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>

<template>
  <button>{{ t('workspace.backHome') }}</button>
</template>
```

Adding new copy: prefer adding keys under an existing group in `zh-CN.js`, then sync to other locales (can be left empty to fall back).

## Data Safety

- The entire `data/` directory is excluded by `.gitignore`, so project data never leaks into the repo
- API keys never enter the repo; `.env` is also in `.gitignore`; keys entered in the UI are stored only in the local `data/app.db`
- All AI calls go directly to the provider you configured; this tool does not collect, forward, or report any data

## Roadmap

Completed:

- Phase 1: Home / project list
- Phase 2: Workspace / chapter management
- Phase 3: Editor + AI generation (full chapter / continue / rewrite selection / summary, SSE streaming with interrupt)
- Phase 4A: Character profiles + AI extraction
- Phase 4B: Relationship graph + plot timeline + consistency check
- AI reverse injection (character profiles + recent plot thread + worldbuilding entries + snapshot before this chapter + in-progress tasks)
- Project import/export (full JSON backup / Markdown reading export)
- Model config UI (presets: Claude / OpenAI / DeepSeek / Qwen / Kimi / Gemini / Ollama / custom)
- Phase 5: Worldbuilding wiki (locations / organizations / items / concepts)
- Phase 6: Progression systems (multiple ladders, auto-seeded by genre) + stateful event sourcing + task list + timeline overlay of character change trajectories
- Phase 7: Chapter version history (auto-snapshot + manual tagging + diff comparison + per-entry restore / delete)
- Phase 8: Chapter scoring (4-dimension scoring + historical trend) + AI style check (picks AI-flavored paragraphs + one-click jump-to-rewrite) + dual-role model (independent writing / reviewing config)
- Phase 9: Story consistency pipeline (synopsis → main threads → beats → event extraction → beat-event reconciliation → consistency issue status tracking) + AI prompt preview
- Phase 10: MCP integration (exposes all domain data + chapter-writing tool via Model Context Protocol to Claude Code / Claude Desktop / Cursor; read on by default, write requires env toggle + auto version-snapshot safety net)
- Phase 11: Outline mode (batch AI-draft titles / summaries / beats for N consecutive chapters, persisted as `outlined` placeholder chapters; body tab adds chapter-outline reconciliation, item-by-item covered / partial / missing)
- Phase 12: Author voice + objective style signals (project-level verbal tics / style description auto-injected into prompt; style check ships 6-dimensional statistical signals — see [docs/author-voice-and-style-signals.md](docs/author-voice-and-style-signals.md))

Candidates: chapter volumes, timeline character-swimlane visualization, generation-result comparison / regeneration, cross-model scoring comparison view, full-text chapter search via MCP tools.

## License

[AGPL-3.0](LICENSE)

> Note: AGPL-3.0 requires **network services** to be open-sourced too — if you modify this repo and offer it as a service to others (SaaS / public deployment / hosted for clients), you must release your modifications under AGPL-3.0 as well. Local personal use, internal company use, and study/research are unaffected.
