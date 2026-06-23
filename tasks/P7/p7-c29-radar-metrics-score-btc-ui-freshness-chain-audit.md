# P7-C29 / Radar Metrics -> Module Score -> BTC Card -> Vue UI Freshness Chain Audit

## 状态
DONE

## 背景

Radar Runtime 已经改为常驻 daemon，并且 P7-C28 已经把剩余 missing/stale feature 的主要断点修到：

```text
runtime_fresh = true
source_missing_module_count = 0
source_stale_module_count = 0
```

但当前还需要一次更细的业务审计，确认：

```text
每个 radar 的底层指标是否真实按 cadence 更新
每个 radar 的综合分是否由这些指标正确融合
BTC 主卡是否消费 runtime cockpit / P4.5 cockpit 的正确字段
Vue UI 是否正确展示 runtime freshness、source freshness、score、direction、stage、support/pressure
```

这张任务卡的目标不是重写算法，而是完整审计链条，找出任何“数据新鲜但 UI 未响应”“模块详情分数变化但 BTC 主卡不敏感”“source partial 被误显示为 healthy/fresh”等断层。

## 审计范围

覆盖 14 个 radar modules：

```text
macro_radar
dollar_liquidity
treasury_credit
kline_orderflow
derivatives_crowding
fund_flow
btc_adoption
onchain_valuation
trade_structure_flow
options_volatility
crypto_breadth
asia_risk
event_policy
btc_total_state
```

覆盖链条：

```text
P1 source / metric_values
P2 metric registry / feature extraction
P3 module payload / module_semantic_profile
P4.5 btc_trend_cockpit / btc_runtime_cockpit
P8 SQLite snapshots
P9 FastAPI
P5 Vue3 dashboard / radar detail / BTC main card
P7 audit HTML
```

## 核心审计问题

### 0. 数据链条断层审计

对每个 radar module、BTC 主卡、Vue UI 显示字段建立一条可追溯链：

```text
source_config
  -> source_run
  -> raw_observation
  -> normalized metric_value
  -> feature record
  -> module payload
  -> module runtime snapshot
  -> btc_runtime_cockpit / btc_trend_cockpit
  -> FastAPI response
  -> Vue computed/render field
```

每一段必须输出：

```text
upstream_id
downstream_id
asof_ts / collected_at / created_at
freshness_state
record_count
join_key
status = pass|partial|fail
break_reason
```

断层定义：

```text
source 有最新数据，但 metric_values 没有对应 row
metric_values 有最新数据，但 module payload 没消费
module payload 有分数，但 runtime snapshot module_score 为 0 或 missing
runtime snapshot 有 cockpit，但 API 没透传
API 有字段，但 Vue UI 没消费或显示 fallback/mock
Vue UI 显示 fresh，但 API/HTML 显示 stale/missing
```

断层严重度：

```text
critical:
  BTC 主卡、fast layer、direction/score 字段断层

high:
  radar module_score、source_freshness、signal_stage 断层

medium:
  support/pressure/conflict drivers、detail panel、audit text 断层

low:
  context-only、expected_lag、slow regime explanatory fields 断层
```

### 1. 指标层

逐模块确认：

```text
metric_id 是否存在 registry
source_id 是否存在 SOURCE_CONFIGS
source_run_id 是否可追溯
metric_values 是否有最新 row
freshness_status / collection_freshness_status / business_recency_status 是否合理
quality_blocking 是否只标记真正会影响方向/确认的指标
context_only / expected_lag / optional metric 是否不会阻断 fast signal
```

### 2. Radar 综合分层

逐模块确认：

```text
module_score 是否来自模块 payload 或 module_semantic_profile
module_effective_score 是否与模块详情页中间综合分一致或有可解释映射
module_direction / module_effective_direction 是否与 score 符号和 drivers 一致
signal_stage 是否符合 score、acceptance、residual、data quality
support_drivers / pressure_drivers / conflict_drivers 是否来自当前 payload，不是旧 fallback
```

### 3. BTC 主卡层

确认 BTC 主卡显示来源：

```text
优先 btc_runtime_cockpit
同时保留 P4.5 btc_trend_cockpit acceptance/residual gate
runtime fast layer 变化 1-2 tick 内能改变 fast read / dominant pressure/support
confirmed_signal 仍必须走 P4.5 acceptance/residual，不被单个 runtime module 覆盖
主卡颜色、分数、文案与 cockpit headline_stage / trend_quality / net_score 一致
```

### 4. Vue3 UI 层

确认前端每个位置使用正确字段：

```text
Radar Overview 卡片：
  module_score
  module_effective_direction
  signal_stage
  source_freshness.state

Radar Detail 子页：
  top support/pressure/conflict metrics
  center module card color
  source group / refresh gate / stale samples

BTC 主卡：
  runtime/source 双层 freshness
  fast/confirmation/regime score
  support/pressure/conflict
  confirmation/invalidation text

Audit drawer / right panel:
  API 返回值与 HTML 审计一致
```

## 必须对齐的 API

```text
GET /api/radar-runtime/daemon/status
GET /api/radar-runtime/modules/latest
GET /api/radar-runtime/cockpit/latest
GET /api/p45/dashboard/latest
GET /api/p45/radar-modules/latest
GET /api/p45/radar-modules/{module_id}
```

## SQLite 审计点

必须能按最新 snapshot 串起来：

```text
source_runs.run_id
raw_observations.source_id
metric_values.metric_id/source_id/source_run_id
module_json_outputs.run_id/module_id
radar_module_snapshots.module_snapshot_id
radar_runtime_snapshots.runtime_snapshot_id
```

## 审计输出

新增或增强：

```text
reports/radar-metrics-score-btc-ui-chain-audit.html
reports/radar-metrics-score-btc-ui-chain-audit.md
```

HTML 必须包含：

```text
1. 总览：PASS / PARTIAL / FAIL
2. 数据链条断层矩阵 source -> metric -> module -> cockpit -> API -> UI
3. 14 模块指标新鲜度矩阵
4. 14 模块综合分映射表
5. BTC runtime cockpit 与 P4.5 cockpit 对照
6. API 字段透传检查
7. Vue UI 字段消费检查
8. SQLite lineage 检查
9. 断点列表和修复建议
```

## DoD

1. 每个 radar module 至少列出 top metrics、module_score、effective_direction、signal_stage、freshness state。
2. 14 个模块的 `module_score` 不允许全为 0，若为 0 必须有 neutral/insufficient evidence 原因。
3. `module_score` 与 radar detail 中间综合分一致，或审计报告给出映射来源。
4. `source_freshness.state`、`runtime_freshness.state`、`participation_policy` 在 API 和 UI 语义一致。
5. BTC 主卡的 fast/confirmation/regime 分数来自 `btc_runtime_cockpit.scores` 或明确 fallback。
6. BTC 主卡的 confirmed 结论仍受 P4.5 acceptance/residual gate 控制。
7. Radar detail 中心卡颜色由 `module_score + signal_stage + support/pressure + effective_direction` 共同决定。
8. Vue3 UI 没有使用 mock/static fallback 覆盖真实 API 字段。
9. SQLite 能从主卡追溯到模块 snapshot，再追溯到 module payload 和 metric_values。
10. 数据链条断层矩阵必须覆盖 14 个 module 和 BTC 主卡关键字段。
11. 任一 critical/high 断层必须让整体审计 FAIL，不能被 freshness PASS 掩盖。
12. partial/live/expected_lag 只能标记为 PARTIAL，必须给出不影响方向的原因。
13. 审计 HTML 使用最新 runtime snapshot，显示 snapshot_id/asof_ts，不能使用旧文件误判。
14. `pytest` 相关后端测试通过。
15. `npm run build` 通过。

## 验收命令

```powershell
$env:PYTHONPATH='E:\onlyBTC\backend\src'

# 1. 触发 radar runtime run once
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/run-once' -Method Post

# 2. 生成/刷新审计 HTML
.\.venv\Scripts\python.exe scripts\generate_radar_metrics_score_btc_ui_chain_audit.py

# 3. 检查 API
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/daemon/status' | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/modules/latest' | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/cockpit/latest' | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/p45/dashboard/latest' | ConvertTo-Json -Depth 10

# 4. 回归
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radar_runtime_daemon.py -q
cd frontend
npm run build
```

## PASS / PARTIAL / FAIL 判定

PASS：

```text
14 modules 数据链条完整
source/runtime freshness 可解释
module score 与 UI 展示一致
BTC 主卡能真实响应 runtime fast changes
HTML/API/UI 三方 snapshot 一致
```

PARTIAL：

```text
存在 official/provider expected_lag 或 partial_live，但已明确降级且不影响 fast runtime 判断
```

FAIL：

```text
UI 显示 healthy 但 API/HTML 为 stale/missing
module detail score 与 runtime module_score 不一致且无映射说明
BTC 主卡不消费 runtime cockpit 或变化明显滞后
SQLite 无法追溯到 metric/source lineage
存在 critical/high 数据链条断层
```


## ????

- ???????`reports/radar-metrics-score-btc-ui-chain-audit.html`
- ???????`reports/radar-metrics-score-btc-ui-chain-audit.md`
- ???????PARTIAL?? FAIL?14 ? module ? 8 ? PASS?6 ? PARTIAL?
- PARTIAL ???? expected-lag / optional / derived lineage?HIBOR?Lightning??? event/onchain ?????????????
- BTC runtime cockpit?P4.5 gate?FastAPI contract?Vue runtime ????? PASS?
- ???`pytest backend/tests/test_radar_runtime_daemon.py -q` ???`npm run build` ???
