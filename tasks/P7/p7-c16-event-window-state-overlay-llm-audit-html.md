# P7-C16 / Event Window 状态机、Overlay 与 LLM Analyzer 第二审计 HTML

## 状态
DONE

## Phase
P7 全链路审计 / Event Window 第二份 HTML

## 背景

第一份 Event Window HTML 已覆盖数据源、provider mesh、fetch lineage 与 SQLite 留痕。第二份审计 HTML 需要覆盖业务裁决层：状态机是否按优先级切换、Emergency Overlay 是否只修改交易权限和 ordinary radar trust、DeepSeek Fed Speech Analyzer 是否只做 tone/relevance/confidence，不直接给 BTC 多空。

## 目标

生成第二份审计页：

```text
reports/event-window-state-overlay-llm-audit-report.html
```

该页面用于审计：

```text
P3-EW State Machine
Emergency Overlay
LLM Fed Speech Analyzer
State / Overlay / LLM boundary
SQLite lineage
FastAPI payload consistency
```

## 审计范围

### 1. P3-EW State Machine 审计

检查以下状态是否按优先级正确切换：

```text
data_quality_blocked
unscheduled_shock_confirmed
event_lock
release_surprise
policy_repricing_shock
fed_tone_shift
pre_event_high_alert
expectation_drift_watch
calendar_monitor
event_neutral
post_event_absorbed
post_event_followthrough
```

必须验证：

```text
unscheduled_shock_confirmed > scheduled calendar states
event_lock > pre_event_high_alert
data_quality_blocked 可以阻断其他状态
post_event_absorbed / followthrough 不可在 actual 未发布时伪造
```

### 2. Emergency Overlay 审计

确认 overlay 只改变：

```text
trade_permission_modifier
confidence_cap
volatility_warning
ordinary_radar_trust
valid_until
reason_codes
```

禁止 overlay 直接改变：

```text
BTC module_score
btc_trend_cockpit score
radar module_score
timescale_judge score
article direction
```

重点检查：

```text
watch_only / reduce_size / avoid_new_position / event_lock
```

是否只是交易权限与雷达可信度覆盖层，不是 BTC score 计算入口。

### 3. LLM Fed Speech Analyzer 审计

使用 DeepSeek API 生成/校验文本分析摘要时，必须确认：

```text
LLM only outputs tone / relevance / confidence / summary
LLM does not output BTC bullish / bearish score
LLM does not override actual / consensus / nowcast
LLM does not directly trigger trade permission
ambiguous / data_dependent can remain ambiguous
```

若 DeepSeek key 缺失或调用失败：

```text
audit_status = degraded
deterministic audit still runs
HTML clearly marks deepseek_unavailable
```

## 输入

```text
/api/event-window/latest
/api/event-window/active
/api/event-window/sources/status
/api/event-window/history
SQLite event_watchtower_snapshots
SQLite event_alerts
SQLite event_llm_analyses
SQLite event_official_text_items
SQLite event_source_fetches
```

## 输出

```text
reports/event-window-state-overlay-llm-audit-report.html
reports/p7-c16-event-window-state-overlay-llm-audit.md
```

HTML 至少包含：

```text
1. State Machine Verdict
2. State Priority Trace
3. Emergency Overlay Boundary
4. Score Isolation Check
5. DeepSeek / LLM Analyzer Boundary
6. Official Text / Speech Analysis Samples
7. API vs SQLite Consistency
8. PASS / PARTIAL / FAIL Verdict
```

## DeepSeek 使用规则

```text
Use DeepSeek API only for audit explanation and Fed text tone/relevance review.
Never let DeepSeek be the sole source of pass/fail.
Deterministic contract checks are primary.
DeepSeek output must be cached or hash-deduped where possible.
```

## DoD

- [x] 生成 `reports/event-window-state-overlay-llm-audit-report.html`。
- [x] 生成 `reports/p7-c16-event-window-state-overlay-llm-audit.md`。
- [x] HTML 能展示当前 state priority 是否符合预期。
- [x] HTML 能展示 overlay 没有直接修改 BTC / radar / cockpit score。
- [x] HTML 能展示 watch_only / reduce_size / avoid_new_position / event_lock 的来源和 valid_until。
- [x] HTML 能展示 DeepSeek analyzer 的 provider、model、状态、hash、置信度与边界检查。
- [x] DeepSeek 缺失时不失败，标记 degraded。
- [x] run once 后 API payload 与 SQLite latest snapshot 一致。
- [x] 单元测试或脚本校验覆盖 state priority、overlay score isolation、LLM no-BTC-direction boundary。

## 依赖

- P2-C40
- P3-C56
- P4.5-C46
- P8-C35
- P8-C36
- P9-C40
- P9-C41
- P9-C43
