# 作者声音与风格信号（Author Voice & Style Signals）设计方案

> 状态：已实现（S1-S3 合并到 main，commit `efacb96`）
> 日期：2026-06-27
> 原始规划：todo/P4-ai-detection-strategy.md（已归档到本文档）

## 1. 背景与目标

### 用户场景

平台对 AI 写作的政策在收紧（KDP / Wattpad / Webnovel），同时检测器迭代很快。
"刷分到检测器阈值以下"是条死路：合规风险高、军备竞赛、后置擦除效果有限。

更稳的方向是 **在生成阶段就让产物更接近人类写作分布**：
- 作者把个人语癖、风格偏好沉淀下来
- 每次生成时自动注入到 prompt
- 配合可量化的客观信号让作者**知情决策**，不做"自动到阈值以下"的闭环

### 设计目标

- 把 AI 痕迹问题当作"产品定位问题"而非"对抗检测器问题"
- 数据层用最小表结构承接（一项目一份 profile）
- AI 调用零增加，全部走前置注入，不引入新的 LLM 调用路径
- 客观信号纯本地算，无神经网络依赖、无 ~2GB 模型包

## 2. 数据模型决策

### 新增

| 表 / 字段 | 用途 |
|---|---|
| `author_voice_profiles` 表 | 项目级声音档案 `(project_id 唯一)` |
| `chapter_style_checks.signals` JSON | 每次 AI 文风检查附带的客观统计信号 |

### 关键决策

- **一项目一份 profile**：不做"作者级跨项目复用"。当前阶段加一层"作者 → 项目"间接性是过度抽象；真有第二个项目想共享时再说。
- **profile 字段最小化**：只 `quirks(JSON list)` + `style_notes(TEXT)`。复杂结构（节奏参数 / 对白比例目标 / 句长方差范围）留到真有需求时再加。
- **不改 prompt 模板**：注入在 `chapter_ai_service` 把 messages 拼好之后、调 LLM 之前，appendto 第一条 system message 末尾；不改 `prompts.py` 或 prompt template 表。
- **signals 字段先单写后用**：每次 style_check 算一遍存进 JSON，不抽到独立表，避免表蔓延。
- **不做神经 detector**：Binoculars / GLTR 思路要 transformers + torch，~2GB；Windows 装不上，且把项目拖向"军备竞赛"方向。改作 P6 工作项 5（暂缓）。
- **不做整章重写 service**：现有 `chapter_style_check` 已能"挑句 + 出改写建议 + 一键定位"，整章一次性多样化重写在产品定位上和它重叠。改作 P6 工作项 6（暂缓）。

## 3. 实施里程碑

### S1 — voice profile 表 + CRUD（commit `efacb96`）

- 表：`author_voice_profiles(id, project_id 唯一, quirks JSON, style_notes TEXT, created_at, updated_at)`
- 路由：`GET / PUT / DELETE /api/projects/{id}/voice-profile`
- `PUT` 是 upsert 语义：一项目至多一份，所以不开 `POST`
- schema 层做数据清洗：`quirks` 自动 strip 空白、单条上限 200 字、整体上限 30 条防止 prompt 爆炸
- `service.build_prompt_fragment()` 返回拼好的中文块（标题 + 风格描述 + 语癖清单），空 profile 返回空串便于调用方安全拼接

### S2 — 生成端注入（commit `efacb96`）

- `chapter_ai_service._inject_voice_profile()` 把片段 append 到第一条 system message 末尾
- 没有 system message（rewrite 模板首条是 user）时插一条 system
- 三个入口：`_assemble_generate_messages` / `_assemble_continue_messages` / `_assemble_rewrite_messages` 都接通
- preview-prompt 接口走同一条注入路径 → 前端"所见即所发"

### S3 — 客观风格信号（commit `efacb96`）

- 新模块 `app/services/style_signals.py`，纯 stdlib（无 jieba 等分词依赖）
- 输出 6 维信号：
  - 句子：count / mean_len / stdev_len / p10 / p50 / p90
  - 段落：count / mean_len / stdev_len
  - 词汇丰富度：去重字符 / 非空白字符
  - 标点密度：标点字符 / 总字符
  - 对白占比：引号开头段 / 总段数
- 每次 `style_check_chapter` 同步算一遍落 `chapter_style_checks.signals`
- 旧表升级走 `_NEW_COLUMNS` 轻量迁移：`ALTER TABLE chapter_style_checks ADD COLUMN signals JSON NOT NULL DEFAULT '{}'`

### UI — 前端集成（commit `efacb96`）

- 新增 `VoiceProfileDialog.vue`：顶栏「系统设置 → 作者声音」入口
  - 语癖清单：输入框 + 6 条预设快速添加
  - 风格描述：textarea + 5 条预设可点击插入
  - 清空整份档案按钮（带二次确认）
- 改 `ChapterStyleDialog.vue`：在 issues 上方加客观风格信号折叠面板
  - 默认折叠，6 个指标卡片网格展示
  - 说明文字明确"这是统计参考，不是 AI 痕迹分"

## 4. 服务层结构

```
backend/app/
  models/author_voice_profile.py        # S1: 表
  schemas/author_voice_profile.py       # S1: Pydantic + 数据清洗
  services/author_voice_service.py      # S1: CRUD + build_prompt_fragment
  services/style_signals.py             # S3: 客观信号本地计算
  services/chapter_ai_service.py        # S2: _inject_voice_profile 钩入 3 个入口
  services/chapter_style_check_service.py  # S3: 落 signals
  api/author_voice.py                   # S1: GET/PUT/DELETE 路由
```

## 5. API 一览

```
作者声音
  GET    /api/projects/{id}/voice-profile     # 没建过返回 null,不报 404
  PUT    /api/projects/{id}/voice-profile     # upsert
  DELETE /api/projects/{id}/voice-profile

章节文风检查（已存在,扩展 response 增加 signals 字段）
  POST   /api/chapters/{id}/style-checks
  GET    /api/chapters/{id}/style-checks
```

## 6. Prompt 注入示例

voice profile 存为：

```json
{
  "quirks": ["段落末尾常用半句留白", "少用形容词堆砌"],
  "style_notes": "偏短句白描,平均句长 12-18 字"
}
```

注入到 system message 末尾的实际文本：

```
【作者声音】
本作的写作要保留以下个人风格特征,不要被通用 AI 文风覆盖:

偏短句白描,平均句长 12-18 字

个人语癖(尽量自然融入,不要刻意堆砌):
- 段落末尾常用半句留白
- 少用形容词堆砌
```

## 7. 测试覆盖

- 22 个新测试，合并后全套 332 个测试全绿
- 关键覆盖：
  - voice CRUD：9 cases（GET/PUT/DELETE 全路径 + 空 profile + 30 条上限 + 数据清洗）
  - prompt 注入：5 cases（generate/continue/rewrite 都注入 + 空 profile 不塞空块 + system 末尾位置）
  - style_signals：8 cases（空文本安全 / 句段切分 / 词汇丰富度高低对比 / 对白识别 / 方差为零 / 百分位单调 / 标点比例区间）

## 8. 设计取舍 / 不做项

| 项 | 决策 | 原因 |
|---|---|---|
| 神经 detector（Binoculars / GLTR） | 暂缓，挂到 [P6 工作项 5](../todo/P6-export-polish.md#工作项-5ai-痕迹神经-detector) | ~2GB 依赖 + 项目定位走偏 |
| 整章风格多样化重写 service | 暂缓，挂到 [P6 工作项 6](../todo/P6-export-polish.md#工作项-6章节风格多样化重写) | 与现有 style_check 改写链路重叠 |
| 作者级跨项目 voice 复用 | 不做 | 过度抽象，第二个项目想复用时再说 |
| 句长方差范围 / 对白比例目标 等结构化参数 | 不做 | 模糊性更高的 `style_notes` 自然语言已能表达 |
| 检测分数 / AI-likeness 分数 | 不做 | 是产品定位陷阱，文档明确不做黑盒分数 |

## 9. 验证标准（待跑）

工程层就绪但**没真跑过**：

- 同一 voice profile 生成 5 章后，作者主观判断与不开 profile 的产物有差异
- 客观信号在带 / 不带 profile 时朝预期方向移动（句长方差变大、对白占比可见波动）

这一步只能人工跑，不在工程范围内。

## 10. 风险与提示

- **用户预期管理**：UI 上「客观风格信号」面板写明"这是统计参考，不是 AI 痕迹分"，避免被理解成"刷分工具"。
- **不在产品文案上承诺"绕过检测"**：宣传定位是"保留作者个人风格"，而非"对抗 AI 检测器"。
- **profile 长度上限**：`style_notes` 4000 字，`quirks` 30 条，从 prompt token 预算反推，避免吃掉总上下文。

## 11. 相关文件指针

### 后端
- 模型：[backend/app/models/author_voice_profile.py](../backend/app/models/author_voice_profile.py)
- 服务：[backend/app/services/author_voice_service.py](../backend/app/services/author_voice_service.py)、[backend/app/services/style_signals.py](../backend/app/services/style_signals.py)
- 注入点：[backend/app/services/chapter_ai_service.py](../backend/app/services/chapter_ai_service.py) `_inject_voice_profile`
- 路由：[backend/app/api/author_voice.py](../backend/app/api/author_voice.py)

### 前端
- 弹窗：[frontend/src/components/VoiceProfileDialog.vue](../frontend/src/components/VoiceProfileDialog.vue)
- 信号面板：[frontend/src/components/ChapterStyleDialog.vue](../frontend/src/components/ChapterStyleDialog.vue)
- 入口：[frontend/src/views/WorkspaceView.vue](../frontend/src/views/WorkspaceView.vue)（顶栏「系统设置 → 作者声音」）
- API client：[frontend/src/api/voiceProfile.js](../frontend/src/api/voiceProfile.js)

### 测试
- [backend/tests/test_author_voice.py](../backend/tests/test_author_voice.py)
- [backend/tests/test_voice_profile_injection.py](../backend/tests/test_voice_profile_injection.py)
- [backend/tests/test_style_signals.py](../backend/tests/test_style_signals.py)
