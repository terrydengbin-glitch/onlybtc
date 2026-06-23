# P5-C81 / Event Watchtower LLM 判断入 UI

## 背景

Event Window 已经具备 LLM Fed Speech Analyzer / state-overlay LLM 审计输出，并生成中文解释。当前这些判断主要存在于审计 HTML 或明细表中，Event Watchtower 子页面没有形成清晰的 LLM 判断展示区，用户无法在主 UI 内快速看到：

- LLM 判断的是哪类文本或事件。
- tone / relevance / confidence / boundary 是否通过。
- LLM 是否只做解释与政策语义分类，而没有直接给 BTC 多空。
- 中文总结、原因、边界和可用性。

## 目标

在 Event Watchtower 子页面中加入 LLM 判断展示，不破坏当前页面结构，作为独立解释层嵌入现有 `Speeches` / `History` / `Live` 辅助区。

## 边界

- 不改 Event Window backend 评分逻辑。
- 不让 LLM 直接改变 BTC score、radar score 或 emergency overlay。
- 不读取审计 HTML 文件作为业务输入。
- UI 数据必须来自 FastAPI / SQLite 结构化字段：
  - `fed_speech_monitor`
  - `llm_analyses`
  - `/api/event-window/speeches`
  - `/api/event-window/history`
  - audit bundle summary 只作为链接/审计入口，不作为主数据源。
- 不破坏 Event Watchtower 当前三栏布局、浮窗、critical overlay。

## UI 排版方案

### 1. Live 页：新增轻量 LLM Insight 卡

位置：

```text
Live 主内容中部，Fed Speech / Current Alert 下方或右侧辅助栏内。
```

展示：

```text
LLM Policy Read
provider: deepseek · status: success · boundary pass
tone: balanced / hawkish / dovish / data_dependent / not_policy_relevant
relevance: high / medium / low
confidence: 0.90

中文摘要：
...

边界：
LLM 只做政策语义与事件解释，不直接输出 BTC 多空。
```

原则：

- Live 页只展示最新一条或最重要一条。
- 如果无 high relevance，则显示 `No high-relevance policy text detected`。
- 若 `boundary_pass=false` 或 `confidence<0.7`，显示黄色/红色 guard。

### 2. Speeches 页：新增 LLM Analysis Table

位置：

```text
Speeches tab 内，官方文本列表下方或替换当前空泛 speech 区域。
```

字段：

```text
analysis_id
provider
status
speaker/title
tone
confidence
relevance
boundary_pass
summary_cn
source_time
```

交互：

- 点击一行展开详情。
- 详情显示：
  - 中文摘要
  - 原因
  - 边界说明
  - source lineage / evidence id
  - `does_not_change_btc_score=true`

### 3. History / Audit 区：保留审计 HTML 入口

位置：

```text
History 或 Diagnostics 区块。
```

展示：

```text
Audit HTML 2: State / Overlay / LLM Audit
Open report
snapshot_id / asof_ts
```

注意：

- HTML 是审计产物，不参与业务流。
- UI 展示 structured LLM payload，HTML 只做核查入口。

## 视觉规范

- `tone=hawkish`：amber / pressure 语义色。
- `tone=dovish`：teal / support 语义色。
- `tone=balanced|data_dependent`：blue / mixed。
- `not_policy_relevant`：muted。
- `boundary_pass=false`：red guard。
- 卡片圆角、边框、字体沿用 Event Watchtower 现有样式，不新增独立视觉体系。

## DoD

- [x] Event Watchtower Live 页出现 LLM Policy Read 卡。
- [x] Speeches 页出现 LLM Analysis Table。
- [x] 每条 LLM 分析显示 provider / status / tone / confidence / relevance / boundary。
- [x] 中文 summary 可见，不需要打开 HTML。
- [x] 点击分析行可展开详情。
- [x] UI 明确显示 LLM 不直接改变 BTC score。
- [x] `boundary_pass=false`、`confidence<0.7` 有明显视觉提示。
- [x] 数据来自 FastAPI / SQLite payload，不从 HTML 反向读取。
- [x] 不破坏 Event Watchtower 当前 Live 三栏布局和全局浮窗。
- [x] `npm run build` 通过。
