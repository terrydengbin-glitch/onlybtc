# P7-C28 / Radar Runtime Stale Feature Targeted Repair & Full-chain Audit

## 状态

DONE

## Acceptance Snapshot

```text
runtime_fresh = true
source_missing_module_count = 0
source_stale_module_count = 0
radar-runtime-audit-report overall_status = PASS
```

## 背景

P9-C54 已经补上 Radar Runtime Source Refresh Gate：

```text
runtime tick 前会执行 targeted source refresh
last_source_refresh_gate.status = success
gate_sources = 45
gate_failed = 0
runtime_fresh = true
14/14 modules runtime fresh
```

但最新审计仍显示：

```text
source_fresh = false
source_freshness_state = stale
source_stale_module_count = 1
source_missing_module_count = 5
```

当前需要定点修复的模块：

```text
derivatives_crowding
trade_structure_flow
macro_radar
treasury_credit
options_volatility
asia_risk
```

这说明链条已经从“runtime 没刷新 source”收敛为更具体的断点：

```text
1. 某些模块的 feature/source mapping 不完整。
2. 某些 quality_blocking feature 的 source_id 没有进入 runtime source group。
3. 某些 expected_lag / context-only / fallback feature 仍被当成 blocking missing/stale。
4. P1 collect 已经成功，但 P2/P3 module payload 没有正确引用本轮或最新可用 feature。
5. API/UI/HTML 需要把 source_missing / source_stale 的真实原因展示出来，而不是只显示 stale。
```

## 目标

对 6 个 remaining stale/missing modules 做定点审计和修复，确保 P1 数据采集、P2/P3 feature 映射、P8 SQLite 持久化、P9 FastAPI 透传、P5 Vue3 展示、P7 审计 HTML 全链条一致。

最终目标：

```text
runtime_fresh = true
fast modules source_fresh = true 或 partial_live
slow/regime modules 不因 expected_lag 被误判为 blocking stale
source_missing_module_count = 0
source_stale_module_count 降到 0，或只保留可解释 provider_stale_suspect
BTC 主卡能明确显示 runtime/source 双层可信度
```

## 范围

涉及：

- P1 source registry / collect_sources / derived metric backfill
- P2 radar metric registry / module metric-source mapping
- P3 radar feature payload / quality_blocking / selected feature 口径
- P8 SQLite metric_values / module_json_outputs / radar_runtime_snapshots
- P9 radar-runtime API / source refresh gate contract
- P5 Vue3 runtime health / radar detail stale reason display
- P7 radar-runtime-audit-report.html

不涉及：

- 重写 radar module 核心算法
- 改变 P4.5 acceptance/residual confirmed gate
- 让 UI 直接覆盖 source freshness 结果
- 把 slow macro/onchain data 强行按 1m/5m 频率刷新

## 上下游链条

### 1. P1 Source Layer

需要确认每个 stale/missing module 的真实 source 依赖：

```text
derivatives_crowding:
  binance-btcusdt-funding
  binance-btcusdt-open-interest
  binance-btcusdt-kline-5m/15m/1h
  binance-btcusdt-global-long-short-account-ratio
  binance-btcusdt-top-long-short-account-ratio
  binance-btcusdt-top-long-short-position-ratio
  binance-btcusdt-taker-buy-sell-ratio
  liquidation sources if referenced

trade_structure_flow:
  binance-btcusdt-kline-5m/15m/1h
  binance-btcusdt-taker-buy-sell-ratio
  liquidation / price acceptance / execution friction sources

macro_radar:
  FRED / TradingView macro market proxy
  DXY, real yield, 2Y, 10Y, NASDAQ, S&P, VIX, oil/gold where used

treasury_credit:
  Treasury/FRED credit and yield sources
  IG/HY spreads, breakeven, curve, credit pressure derived metrics

options_volatility:
  deribit-btc-options
  binance 1d realized volatility proxy
  options context sources

asia_risk:
  TradingView USDJPY / USDCNH / Nikkei / JGB / TOPIX / Hang Seng Tech
  asia-risk-derived
```

P1 修复要求：

```text
source_id 存在于 SOURCE_CONFIGS。
source_id 是 collectable，不能被 runtime gate 配置但 registry 缺失。
collect run 成功后 metric_values 有对应 latest row。
derived metrics 的 source_run_id / source_id / run_mode 不为空。
```

### 2. P2/P3 Feature Layer

需要逐模块审计：

```text
module_payload.features 中的 metric_id 是否注册。
feature.source_id 是否存在。
quality_blocking 是否只给真正影响方向/确认的指标。
context_only / audit_only / fallback_reference 不得标记 quality_blocking=true。
expected_lag slow feature 不得让 fast module source_fresh=false。
current_run_has_value / selected_reason / feature_run_scope 口径是否正确。
```

修复原则：

```text
fast trigger feature stale => 可以阻断 fast confirmed。
slow context feature expected_lag => 只降 confidence，不阻断 runtime。
missing optional feature => quality_discounted，不是 blocked。
missing required feature => source_missing，需要明确 missing_reason。
```

### 3. P8 SQLite

必须确认数据落库链条：

```text
source_runs 有 targeted source_refresh_gate run_id。
raw_observations 有对应 source_id。
metric_values 有对应 metric_id/source_id/run_mode。
module_json_outputs 有 module payload。
radar_module_snapshots 保存 source_group_id / source_refresh_status / source_freshness。
radar_runtime_snapshots 保存 last_source_refresh_gate / health / btc_runtime_cockpit。
```

若 SQLite 有数据但 module 仍 missing，需要定位为：

```text
feature lookup mapping issue
historical_window selection issue
metric_id mismatch
source_id mismatch
quality gate mismatch
```

### 4. P9 FastAPI

以下 API 必须可解释透传：

```text
/api/radar-runtime/daemon/status
/api/radar-runtime/modules/latest
/api/radar-runtime/cockpit/latest
/api/p45/dashboard/latest
```

新增或确认字段：

```json
{
  "source_freshness": {
    "state": "fresh|partial_live|expected_lag|stale|expired|missing",
    "missing_feature_count": 0,
    "stale_feature_count": 0,
    "expected_lag_feature_count": 0,
    "context_only_stale_count": 0,
    "sample": []
  },
  "source_refresh_gate": {},
  "source_group_id": "",
  "source_refresh_status": ""
}
```

### 5. P5 Vue3

前端必须区分：

```text
runtime fresh:
  module snapshot 是否按 cadence 更新

source fresh:
  底层 feature/source 是否可信

source partial_live / expected_lag:
  可用但降置信，不等于错误

source missing/stale:
  需要显示模块和样本原因
```

UI 展示要求：

```text
BTC 主卡显示 runtime/source 双层状态。
Radar detail 显示 source group、source refresh status、missing/stale sample。
Dashboard 不允许只用绿色 fresh 掩盖 source stale。
```

### 6. P7 Audit HTML

`reports/radar-runtime-audit-report.html` 必须能直接回答：

```text
哪个模块 stale/missing？
哪个 feature stale/missing？
这个 feature 是否 quality_blocking？
source_id 是否存在？
最新 source run 是否成功？
metric_values 是否有最新值？
是 expected_lag，还是 provider_stale_suspect，还是 mapping 断层？
```

## 定点模块 DoD

### derivatives_crowding

- [ ] funding / OI / long-short / taker / kline / liquidation 依赖源全部进入 runtime source group。
- [ ] source_refresh_gate 后有对应 metric_values。
- [ ] missing feature 不再来自 source_id mismatch。
- [ ] funding/OI stale 时能明确显示 provider/source 原因。

### trade_structure_flow

- [ ] kline/taker/price acceptance/liquidation 依赖源全部可追踪。
- [ ] fast feature stale 时能被 targeted refresh 修复。
- [ ] optional microstructure proxy missing 不直接 blocked。

### macro_radar

- [ ] FRED/TradingView proxy source 映射完整。
- [ ] FRED expected_lag / publication delay 不误判 fast stale。
- [ ] TradingView realtime fallback 可区分 success / missing / blocked。

### treasury_credit

- [ ] treasury/credit/breakeven/HY/IG source 映射完整。
- [ ] 慢变量按业务日历 freshness policy 判断。
- [ ] credit-derived metrics 有 source_run_id。

### options_volatility

- [ ] Deribit/options/realized-vol proxy source 映射完整。
- [ ] options slow context 不阻断 fast runtime。
- [ ] missing options source 时 UI/API 明确显示 optional/required。

### asia_risk

- [ ] USDJPY/USDCNH/Nikkei/JGB/TOPIX/Hang Seng Tech source 映射完整。
- [ ] FRED FX proxy stale 时优先 TradingView realtime fallback。
- [ ] provider_stale_suspect 能被解释为 source issue，不是 runtime issue。

## 全链路 DoD

- [ ] targeted source refresh gate 成功后，6 个模块不再出现不可解释 missing/stale。
- [ ] `source_missing_module_count = 0`。
- [ ] `source_stale_module_count = 0`，或剩余 stale 都有明确 provider_stale_suspect / access_blocked 解释。
- [ ] fast modules 的 source_freshness_state 为 fresh 或 partial_live。
- [ ] expected_lag slow data 不阻断 BTC runtime fast layer。
- [ ] `btc_runtime_cockpit` 继续使用 P4.5 acceptance/residual gate，不被 runtime source 直接 confirmed。
- [ ] SQLite 中 source_runs / metric_values / module snapshots / runtime snapshots 可按 run_id 串起来。
- [ ] FastAPI 返回 source group、refresh gate、missing/stale sample。
- [ ] Vue3 前端显示 runtime/source 双层状态。
- [ ] `radar-runtime-audit-report.html` 显示每个 remaining stale 的根因和下一步。
- [ ] 后端测试通过。
- [ ] `npm run build` 通过。

## 验收命令

```powershell
$env:PYTHONPATH='E:\onlyBTC\backend\src'

# 1. 后端回归
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radar_runtime_daemon.py backend\tests\test_sources.py -q

# 2. 触发 runtime run once
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/run-once' -Method Post

# 3. 检查 API
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/daemon/status' | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/modules/latest' | ConvertTo-Json -Depth 10
Invoke-RestMethod -Uri 'http://127.0.0.1:8118/api/radar-runtime/cockpit/latest' | ConvertTo-Json -Depth 10

# 4. 生成审计 HTML
.\.venv\Scripts\python.exe scripts\generate_radar_runtime_audit_report.py

# 5. 前端构建
cd frontend
npm run build
```

## 复审判断

PASS 条件：

```text
runtime_fresh = true
source_refresh_gate = success / partial with explained optional failures
source_missing_module_count = 0
source_stale_module_count = 0 或只有解释完整的 provider_stale_suspect
BTC 主卡不再被不明 stale 压成迟钝
审计 HTML 能从 module -> feature -> source -> SQLite -> API -> UI 追溯
```

PARTIAL 条件：

```text
仍有 provider access / paid source / official delay 导致 partial_live，但已明确降级且不影响 fast layer。
```

FAIL 条件：

```text
runtime fresh 但 source missing/stale 无根因。
fast module 使用过期 BTC market source。
UI/API 显示 healthy 但 HTML 显示 source stale。
SQLite 中找不到 source_refresh_gate 对应数据。
```
