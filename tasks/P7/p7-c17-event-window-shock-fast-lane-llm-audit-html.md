# P7-C17 / Event Window Shock Fast Lane 第三审计 HTML 与 LLM 解释

## 状态

DONE

## Phase

P7 全链路审计 / Event Window 第三份 HTML

## 背景

Event Window 已经有两份审计 HTML：

```text
HTML 1: source audit
  数据源、provider mesh、source fetch lineage、SQLite counts

HTML 2: state / overlay / LLM audit
  状态机优先级、Emergency Overlay 边界、Fed Speech LLM 边界
```

P2-C40 引入 `Unscheduled Shock Fast Lane` 后，需要第三份审计 HTML，专门回答：

```text
突发事件是否被真实采集？
突发事件如何影响 Event Window？
是否只改变 emergency overlay，而不直接改变 BTC score？
LLM 是否只做冲击解释 / 风险归类，而不是输出 BTC 多空？
high / critical shock 是否能触发浮窗、事件子页面和 dashboard summary？
```

## 目标

新增第三份审计报告：

```text
reports/event-window-shock-fast-lane-audit-report.html
reports/p7-c17-event-window-shock-fast-lane-audit.md
```

该报告用于审计 P2-C40 的完整业务链条：

```text
official / market / crypto-native shock source
  -> normalized shock item
  -> severity classifier
  -> state machine
  -> emergency overlay
  -> SQLite timeline / snapshot / alert
  -> API
  -> frontend floating alert / event subpage / dashboard summary
  -> LLM Chinese explanation
```

## 突发事件如何影响 Event Window

### 1. watch shock

触发条件：

```text
single trusted source
or rumor with visible market reaction
or weak BTC / cross-asset dislocation without enough confirmation
```

影响：

```json
{
  "event_window_state": "unscheduled_shock_watch",
  "emergency_level": "watch",
  "trade_permission_modifier": "reduce_size",
  "ordinary_radar_trust": "reduced",
  "direct_score_impact": false
}
```

边界：

```text
不允许 event_lock。
不允许改 BTC score。
不允许输出 confirmed shock。
```

### 2. high shock

触发条件：

```text
BTC 5m return z >= 2
or official source hit with non-critical policy relevance
or multi-source trusted hit
or prediction-market / cross-asset repricing with BTC reaction
```

影响：

```json
{
  "event_window_state": "unscheduled_shock_watch",
  "emergency_level": "high",
  "trade_permission_modifier": "watch_only",
  "ordinary_radar_trust": "low",
  "direct_score_impact": false
}
```

边界：

```text
high 可以让 ordinary radar trust 变 low。
high 可以触发浮窗和 dashboard summary 高亮。
high 不允许直接变成 BTC bearish / bullish。
```

### 3. critical shock

触发条件：

```text
official policy / regulatory / exchange / stablecoin critical hit
or BTC 5m return z >= 3 with OI/liquidation/cross-asset confirmation
or cross-asset shock propagates to BTC with microstructure confirmation
```

影响：

```json
{
  "event_window_state": "unscheduled_shock_confirmed",
  "state_priority": 95,
  "emergency_level": "critical",
  "trade_permission_modifier": "event_lock",
  "ordinary_radar_trust": "blocked",
  "direct_score_impact": false
}
```

边界：

```text
critical 覆盖 scheduled calendar / event_lock。
critical 只阻断普通趋势信任，不直接改 BTC score。
critical 必须有 source_url/source_hash 或 market evidence。
```

## LLM 解释边界

LLM 可以做：

```text
shock_type 分类
policy/regulatory/exchange/stablecoin/geopolitical/cross_asset/crypto_native 归因
严重程度解释
source reliability 解释
为什么 overlay 是 reduce_size / watch_only / event_lock
中文摘要
```

LLM 不允许做：

```text
直接输出 BTC bullish / bearish
直接修改 emergency_level
绕过 state machine
把 rumor 升级成 critical
把 non-official source 伪装成 official
```

## 新增输出契约

第三份审计 HTML 应展示：

```json
{
  "schema_version": "p7.event_window_shock_fast_lane_audit.v1",
  "asof_ts": "",
  "pass": true,
  "latest_shock": {},
  "shock_chain": {
    "source_collected": true,
    "normalized": true,
    "classified": true,
    "state_applied": true,
    "overlay_applied": true,
    "sqlite_persisted": true,
    "api_visible": true,
    "frontend_contract_ready": true
  },
  "boundary_checks": {
    "direct_score_impact_false": true,
    "rumor_not_critical": true,
    "critical_overrides_scheduled": true,
    "high_sets_watch_only_not_event_lock": true,
    "official_has_url_hash": true,
    "market_has_evidence": true,
    "llm_no_btc_direction": true
  },
  "llm_interpretation": {
    "provider": "deepseek",
    "status": "success|degraded|not_requested",
    "summary_zh": "",
    "risk_reason_zh": "",
    "action_boundary_zh": "",
    "confidence": 0
  },
  "sqlite_counts": {},
  "api_checks": {}
}
```

## HTML 页面结构

### 1. Shock Chain Banner

显示：

```text
PASS / FAIL / PARTIAL
latest shock state
emergency level
overlay modifier
direct_score_impact=false
```

### 2. Latest Shock Item

显示：

```text
shock_type
confirmation_level
source_count
official_confirmed
market_dislocation
btc_microstructure_confirmation
reason_codes
source_lineage
```

### 3. Event Window Impact

显示 shock 对 Event Window 的影响：

```text
state before / after
state priority
emergency_level
trade_permission_modifier
ordinary_radar_trust
valid_until
```

### 4. Boundary Checks

显示所有边界：

```text
rumor not critical
high not event_lock
critical overrides scheduled
direct_score_impact false
official source has URL/hash
market source has evidence
```

### 5. LLM 中文解释

显示：

```text
突发事件是什么
为什么是 watch/high/critical
为什么只改变 overlay 不改 BTC score
下一步应该等待什么确认
```

### 6. SQLite / API / UI Contract

显示：

```text
snapshot count
timeline count
alert count
shock-lane latest API
shock-lane history API
floating alert contract
dashboard summary contract
```

## DoD

- [ ] 生成 `reports/event-window-shock-fast-lane-audit-report.html`。
- [ ] 生成 `reports/p7-c17-event-window-shock-fast-lane-audit.md`。
- [ ] HTML 显示 latest shock item 或结构化 empty state。
- [ ] HTML 明确显示 shock 如何影响 Event Window state / overlay。
- [ ] HTML 显示 `direct_score_impact=false`。
- [ ] LLM 输出中文解释，并通过 no BTC direction boundary。
- [ ] rumor 不允许 critical 的测试通过。
- [ ] high shock 只能 `watch_only`，不能 `event_lock`。
- [ ] critical shock 能覆盖 scheduled calendar。
- [ ] official shock 必须有 URL/hash lineage。
- [ ] market shock 必须有 BTC/OI/liquidation/cross-asset evidence 至少一种。
- [ ] SQLite snapshot / timeline / alert 能追踪 shock。
- [ ] `/api/event-window/shock-lane/latest` 与 history 可审计。
- [ ] `pytest backend/tests/test_event_watchtower.py -q` 通过。
- [ ] 重新生成 HTML 1 / 2 / 3 后，三份报告链路一致。

## 验收命令

```powershell
$env:PYTHONPATH='backend/src'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_event_watchtower.py -q
.\.venv\Scripts\python.exe scripts\generate_event_window_source_audit_html.py
.\.venv\Scripts\python.exe scripts\generate_event_window_state_overlay_llm_audit_html.py
.\.venv\Scripts\python.exe scripts\generate_event_window_shock_fast_lane_audit_html.py
```

如涉及前端：

```powershell
cd frontend
npm run build
```

## 依赖

- P2-C40
- P3-C56
- P4.5-C46
- P8-C35
- P8-C36
- P9-C40
- P9-C42
- P5-C64
- P5-C65
- P5-C66
