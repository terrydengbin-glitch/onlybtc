# P9-C54 / Radar Runtime Source Refresh Gate

## 状态

DONE

## 当前复审结果

已实现并验证：

```text
source refresh gate 已接入 runtime tick 前置流程。
manual run-once 能执行 targeted LIVE collect。
last_source_refresh_gate 已写入 runtime snapshot。
run-once gate_status = success。
gate_sources = 45。
gate_failed = 0。
runtime_fresh = true。
14/14 modules runtime fresh。
审计 HTML 已展示 Source Refresh Gate Summary / Source Group Mapping / Source Freshness Samples。
后端测试通过。
npm run build 通过。
```

仍未完全 PASS：

```text
source_fresh = false。
source_freshness_state = stale。
source_stale_module_count = 1，当前为 asia_risk。
source_missing_module_count = 5，当前为 derivatives_crowding / macro_radar / options_volatility / trade_structure_flow / treasury_credit。
```

结论：

```text
本卡已修复“runtime tick 前没有 source gate”的链条断点。
剩余问题已经从调度断层收敛为具体 module feature/source mapping 与 quality_blocking 口径问题，需要后续 P1/P2/P3 层继续处理。
```

P9-C56 已关闭剩余 source freshness 断点：

```text
source_stale_module_count = 0
source_missing_module_count = 0
source_fresh = true
source_freshness_state = expected_lag
radar-runtime audit overall_status = PASS
```

## 背景

P9-C53 已经把 Radar Runtime daemon 的常驻调度、SQLite 写锁、runtime/source freshness 双层状态和审计 HTML 打通。重启后审计结果显示：

```text
daemon status = running
daemon health = healthy
runtime_fresh = true
14/14 modules runtime fresh
SQLite lock = ok
```

但同时出现新的业务断点：

```text
source_fresh = false
source_freshness_state = stale
source_stale_module_count = 14
```

这说明 runtime daemon 的模块快照按频率刷新了，但它在刷新模块前没有先刷新或确认对应 P1 底层数据源。于是模块使用的是旧 collect run 中的 feature/source 数据，导致：

```text
runtime fresh != source fresh
模块看似实时更新，但底层 BTC kline / funding / OI / macro / onchain feature 可能已经 stale
BTC 主卡 fast layer 对真实行情变化仍可能迟钝
```

当前 stale 样本包括：

```text
kline_orderflow:
  btc_return_5m / 15m / 1h 等 Binance kline 派生数据 stale

derivatives_crowding:
  funding / open interest / btc_response 等衍生品输入 stale

trade_structure_flow:
  taker / price acceptance / microstructure proxy stale

asia_risk:
  usdjpy / 亚洲时段 BTC response 等 proxy stale 或 provider_stale_suspect

macro / liquidity / treasury / onchain / adoption:
  慢变量有 expected_lag / provider_stale / missing 混合状态
```

因此下一步不是继续修 UI，而是给 Runtime daemon 增加 source refresh gate：每次模块 tick 前，按照模块所属 cadence 和依赖源组，先刷新或确认底层 P1 source，再运行模块分析。

## 目标

让 Radar Runtime daemon 在每次分频刷新前，能够按模块依赖的数据源组执行 targeted source refresh / freshness confirmation，确保：

```text
1. fast modules 使用最新 BTC market / derivatives / orderflow source。
2. confirmation modules 使用合理频率更新的 macro / flow / liquidity source。
3. regime modules 使用 business-calendar-aware 的 slow source，不因 expected_lag 被误判为 blocking stale。
4. source stale 时，模块仍可输出快照，但必须降级参与，不允许污染 BTC 主卡强结论。
5. runtime 审计 HTML 能解释 source 刷新是否成功、哪些 source 仍 stale、是否属于 expected_lag。
```

## 范围

涉及：

- P9 Radar Runtime daemon / scheduler / run-once
- P1 source collection targeted refresh
- P2/P3 module feature freshness gate
- P4.5 / BTC runtime cockpit source participation 降级
- P7 radar-runtime-audit-report.html
- FastAPI runtime health API

不涉及：

- 重写 P1 全量 collector
- 重写 14 个 radar module 业务算法
- 让 runtime 单点覆盖 P4.5 confirmed 结论
- 让 Event Window 参与 radar score
- 用 UI 颜色掩盖 stale source

## 业务规则

### 1. Runtime tick 前必须有 source gate

每次 due modules 被调度时，先根据模块列表计算需要刷新的 source group：

```text
fast_btc_market:
  kline_orderflow
  trade_structure_flow
  derivatives_crowding
  asia_risk

confirmation_macro_flow:
  macro_radar
  dollar_liquidity
  treasury_credit
  fund_flow

regime_slow:
  onchain_valuation
  btc_adoption
  crypto_breadth
  options_volatility
  event_policy
  btc_total_state
```

source gate 行为：

```text
source fresh:
  直接运行 module tick

source stale but targeted refresh success:
  使用刷新后的 source 运行 module tick

source stale and targeted refresh failed:
  运行 module tick，但 source_fresh=false，effective_participation 降级

source expired and quality_blocking:
  不允许参与 confirmed / strong direction，只能 watch / discounted / blocked
```

### 2. Source group mapping 必须显式

新增 runtime source group mapping，禁止隐式猜测。

fast group 最少覆盖：

```text
binance-btcusdt
binance-btcusdt-kline-5m
binance-btcusdt-kline-15m
binance-btcusdt-kline-1h
binance-btcusdt-open-interest
binance-btcusdt-funding
binance-btcusdt-taker-buy-sell-ratio
```

如果某些 source_id 在当前 registry 中不存在，必须在 audit 中显示：

```text
configured_but_missing_source_id
```

不得静默跳过。

### 3. Source freshness gate 要收窄口径

当前 source_freshness 递归扫描 module_payload 内所有 feature，容易把 context-only / audit-only / expected_lag 慢变量误判为 blocking stale。

新规则：

```text
优先统计 quality_blocking=true 的 feature。
如果存在 selected/current/top-contributor feature，只以这些 feature 作为 blocking 判断主口径。
context_only / audit_only / fallback_reference 不得单独导致 module source_fresh=false。
expected_lag / business-calendar lag 只能标记 partial，不得等同 expired。
provider_stale_suspect / hard_stale / expired 才能触发 blocking stale。
```

### 4. 慢变量按业务日历判断

以下数据不应按分钟级 stale 判断：

```text
FRED macro daily/weekly/monthly
onchain slow proxies
ETF / fund flow daily data
official event calendar
options slow context
```

这些数据应输出：

```text
source_freshness_state = partial_live | expected_lag | fresh
```

而不是直接让全模块：

```text
source_freshness_state = stale
```

### 5. BTC 主卡参与规则

Runtime source gate 不能直接覆盖 P4.5 confirmed 机制。

规则：

```text
fast module source fresh:
  可以进入 BTC runtime fast layer

fast module source partial:
  可以进入 fast watch，但降低 sensitivity / confidence

fast module source stale:
  不允许推动 confirmed_signal

P4.5 confirmed:
  仍必须经过 acceptance / residual gate
```

## 输出契约

Runtime snapshot 新增或标准化：

```json
{
  "source_refresh_gate": {
    "run_id": "",
    "started_at": "",
    "finished_at": "",
    "mode": "targeted",
    "module_ids": [],
    "source_group_ids": [],
    "source_ids": [],
    "status": "success|partial|failed|skipped",
    "refreshed_source_count": 0,
    "failed_source_count": 0,
    "missing_configured_source_ids": [],
    "errors": []
  },
  "runtime_fresh": true,
  "source_fresh": true,
  "source_freshness_state": "fresh|partial_live|expected_lag|stale|expired|missing",
  "effective_participation": "full|discounted|watch_only|blocked"
}
```

每个 module snapshot 新增：

```json
{
  "module_id": "",
  "source_group_id": "",
  "source_refresh_status": "success|partial|failed|skipped",
  "source_freshness": {
    "state": "fresh|partial_live|expected_lag|stale|expired|missing",
    "blocking_feature_count": 0,
    "expected_lag_feature_count": 0,
    "context_only_stale_count": 0,
    "sample_blocking_features": []
  }
}
```

## API 要求

以下接口必须透传 source refresh gate：

```text
/api/radar-runtime/daemon/status
/api/radar-runtime/modules/latest
/api/radar-runtime/cockpit/latest
/api/p45/dashboard/latest
```

最少字段：

```json
{
  "runtime_fresh": true,
  "source_fresh": true,
  "source_freshness_state": "partial_live",
  "last_source_refresh_gate": {},
  "source_stale_module_count": 0,
  "source_partial_module_count": 0
}
```

## 审计 HTML 要求

`reports/radar-runtime-audit-report.html` 必须新增：

```text
Source Refresh Gate Summary
Module -> Source Group Mapping
Configured but Missing Source IDs
Blocking Stale Feature Samples
Expected Lag Feature Samples
runtime_fresh vs source_fresh matrix
```

如果 runtime fresh 但 source stale，审计状态不得显示 PASS，只能显示：

```text
PARTIAL
```

如果 fast modules targeted refresh 后 source_fresh=true 或 partial_live，且无 blocking stale，则该部分可 PASS。

## DoD

- [ ] 新增 runtime source group mapping，覆盖 14 个 radar modules。
- [ ] Runtime due module tick 前执行 targeted source refresh 或 freshness confirmation。
- [ ] fast module 刷新前能触发对应 Binance / derivatives / market source refresh。
- [ ] source refresh gate 的 run_id / source_ids / status 写入 runtime snapshot。
- [ ] 14 个 modules 不再因为 context-only / expected_lag 数据被全部判定 source stale。
- [ ] quality_blocking stale feature 仍能正确阻断 confirmed / strong direction。
- [ ] BTC runtime cockpit 显示 runtime_fresh + source_fresh 双层结果。
- [ ] fast source 刷新成功后，fast modules 在 1-2 个 tick 内从 stale 变为 fresh 或 partial_live。
- [ ] `/api/radar-runtime/daemon/status` 显示 last_source_refresh_gate。
- [ ] `radar-runtime-audit-report.html` 显示 source refresh gate 和 stale 样本。
- [ ] P4.5 confirmed 仍必须经过 acceptance / residual gate。
- [ ] 后端测试通过。
- [ ] `npm run build` 通过。

## 验收命令

```powershell
$env:PYTHONPATH='E:\onlyBTC\backend\src'

# targeted source gate 单测 / runtime 回归
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radar_runtime_daemon.py backend\tests\test_sources.py -q

# 手动触发 runtime run once
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/run-once' -Method Post

# 检查 runtime/source freshness
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/daemon/status' | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/modules/latest' | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/cockpit/latest' | ConvertTo-Json -Depth 8

# 审计 HTML
.\.venv\Scripts\python.exe scripts\generate_radar_runtime_audit_report.py

# 前端
cd frontend
npm run build
```

## 人工复审重点

复审时重点看：

```text
1. daemon 是否仍 healthy。
2. runtime_fresh 是否 true。
3. fast modules 的 source_fresh 是否 fresh / partial_live，而不是全部 stale。
4. source_fresh=false 时，UI 是否降级展示而非假装正常。
5. expected_lag 慢变量是否不再污染 fast layer。
6. P4.5 BTC confirmed 是否仍经过 acceptance/residual gate。
7. HTML 和 API 的 snapshot_id / asof_ts 是否一致。
```
