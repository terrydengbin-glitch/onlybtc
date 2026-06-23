# P5-C75 / Event Watchtower 三份审计 HTML 内容入 UI

## 状态

DONE

## Execution Record

### 2026-06-23 / Start

- P5-C73/P5-C74 已完成，按依赖顺序启动 P5-C75。
- 范围限定为 Event Watchtower 子页面、专属样式和必要 computed helper；不改审计 HTML 生成脚本、后端状态机、BTC score、radar score。
- 目标是将 Source Audit、State / Overlay / LLM Audit、Shock Fast Lane Audit 的核心内容用真实 store/API/audit bundle 数据映射到 UI。

### 2026-06-23 / DONE

- Event Watchtower 新增 `Audit` tab。
- 新增 audit computed helper，用于合并 audit bundle reports/file meta、regression、forbidden keys、LLM violations、三份 HTML report 入口。
- `Source Chain Audit` 展示 source mode counts、source quality、provider confidence、provider tiers、fetch lineage 和 secondary/proxy/FedWatch 边界说明。
- `State / Overlay / LLM Audit` 展示 state/overlay 核心字段、reason_codes、`direct_score_impact=false`、forbidden_keys pass、LLM tone/relevance/confidence/speaker/boundary/violations。
- `Shock Fast Lane Audit` 展示 shock 核心字段、event window impact、synthetic regression 状态、boundary checks、LLM 中文冲击解释。
- 三份 HTML 报告入口已接入 `/reports/...html`。
- 验证：`cd frontend && npm run build` 通过。
- 审计报告：`reports/p5-c75-event-watchtower-audit-tab-ui.md`。

## Phase

P5 Vue3 前端展示

## 背景

Event Window 已有三份审计 HTML：

```text
HTML 1: reports/event-window-source-audit-report.html
  数据源 / provider mesh / fetch lineage / SQLite counts

HTML 2: reports/event-window-state-overlay-llm-audit-report.html
  state priority / emergency overlay / Fed Speech LLM boundary / SQLite consistency

HTML 3: reports/event-window-shock-fast-lane-audit-report.html
  shock fast lane / synthetic shock regression / LLM 中文解释 / API checks
```

当前 Event Watchtower UI 只展示了一部分 live 状态，没有把这三份审计 HTML 的核心内容结构化地展示在 Event Window 子页面中。需要把三份 HTML 的审计内容映射到 UI，方便用户不打开 HTML 也能看见链条是否可信。

## 目标

在 Event Watchtower 子页面中新增 `Audit` / `Diagnostics` 视图或整合到现有 `History` tab，使 UI 能展示：

```text
Source Audit
State / Overlay / LLM Audit
Shock Fast Lane Audit
```

所有展示必须来自真实 payload / API / SQLite 统计 / 审计生成结果，不允许手写 mock 数字。

## HTML 1 内容映射：Source Audit

UI 必须展示：

```text
source mode summary:
  overall_source_mode
  live_source_count
  partial_source_count
  fallback_source_count
  failed_source_count

source quality:
  calendar_quality
  actual_quality
  nowcast_quality
  consensus_quality
  fedwatch_quality
  speech_quality

provider confidence:
  calendar_confidence
  consensus_confidence
  nowcast_confidence
  actual_confidence
  rate_probability_confidence
  prediction_market_confidence

provider tiers:
  official
  official_mirror
  secondary_consensus
  secondary_calendar
  prediction_market
  market_implied_proxy
  manual_override
  missing / failed

fetch lineage:
  source_id
  status
  endpoint_url
  parsed_item_count
  error_message
  last_attempt_at / started_at
```

显示边界：

```text
非官方源必须标记 secondary / proxy / prediction_market
consensus missing 时显示 surprise disabled / nowcast risk only
FedWatch proxy 时显示 not CME FedWatch
```

## HTML 2 内容映射：State / Overlay / LLM Audit

UI 必须展示：

```text
state audit:
  event_window_state
  state_priority
  emergency_level
  reason_codes
  valid_until

overlay audit:
  trade_permission_modifier
  confidence_cap
  volatility_warning
  ordinary_radar_trust
  direct_score_impact=false
  forbidden_keys empty / pass

LLM Fed speech audit:
  provider
  status
  tone
  tone_confidence
  policy_relevance
  speaker
  speaker_weight
  requires_human_review
  boundary_passed
  violations
```

LLM 中文解释必须显示，但必须保留边界：

```text
LLM only classifies tone / relevance / confidence.
LLM does not output BTC bullish / bearish.
LLM does not modify emergency_level.
LLM does not modify trade permission.
```

## HTML 3 内容映射：Shock Fast Lane Audit

UI 必须展示：

```text
latest_shock:
  shock_detected
  shock_type
  confirmation_level
  source_count
  market_dislocation
  btc_microstructure_confirmation
  rumor_risk

event window impact:
  state
  overlay
  direct_score_impact=false

synthetic regression:
  critical overrides scheduled
  high watch only
  rumor downgrade
  official url hash lineage

boundary checks:
  direct_score_impact_false
  rumor_not_critical
  critical_overrides_scheduled
  high_sets_watch_only_not_event_lock
  official_has_url_hash
  market_has_evidence

LLM Chinese shock explanation:
  summary_zh
  risk_reason_zh
  action_boundary_zh
  boundary_pass
```

## UI 结构建议

在 Event Watchtower 中新增一个 tab：

```text
Audit
```

或将现有 `History` tab 改为：

```text
Audit / History
```

内部三块：

```text
1. Source Chain
2. State / Overlay / LLM
3. Shock Fast Lane
```

每块都要有：

```text
status pill
key metrics
latest evidence rows
boundary warning
link/open HTML report button
```

## 边界

允许修改：

```text
frontend/src/App.vue Event Watchtower 子页面
frontend/src/styles.css event-watchtower 专属 class
必要 computed helper
```

禁止修改：

```text
审计 HTML 生成脚本
后端状态机
BTC score / radar score
其它页面 UI
```

## DoD

- [x] UI 能看到 HTML 1 的 source/provider/fetch lineage 核心内容。
- [x] UI 能看到 HTML 2 的 state/overlay/LLM boundary 核心内容。
- [x] UI 能看到 HTML 3 的 shock/boundary/LLM 中文解释核心内容。
- [x] UI 中有三份 HTML 报告入口或文件路径提示。
- [x] LLM 中文解释显示为“解释/归因”，不作为交易方向。
- [x] `direct_score_impact=false` 在 audit 区域明确可见。
- [x] `npm run build` 通过。

## 依赖

- P5-C73
- P7-C16
- P7-C17
- P7-C19
