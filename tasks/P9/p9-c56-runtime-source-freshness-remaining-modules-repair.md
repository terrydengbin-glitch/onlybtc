# P9-C56 Runtime Source Freshness Remaining Modules Repair

## 状态

DONE

## Phase

P9 FastAPI / Radar Runtime freshness contract

## Summary

P9-C54 已经把 Radar Runtime source refresh gate 接入调度链路，但复审仍显示 `source_fresh=false`。本任务专门收口剩余 stale / missing modules，使 Dashboard 的 runtime fast layer 不再出现“runtime fresh 但 source freshness 不可信”的断点。

## Scope

本任务只修复 P9-C54 剩余 freshness 断点：

```text
source_stale_module_count = 1
  asia_risk

source_missing_module_count = 5
  derivatives_crowding
  macro_radar
  options_volatility
  trade_structure_flow
  treasury_credit
```

不改变 14 个 Radar module 的交易语义，不新增 BTC 方向判断，不用 UI 隐藏 source stale。

## Business Chain / Contract

```text
P1 targeted source refresh
-> P2/P3 runtime feature payload
-> radar_module_snapshots source_freshness
-> radar_runtime/latest API
-> BTC runtime cockpit participation / Dashboard badges
-> radar-runtime audit report
```

必须保持以下字段可审计：

```text
module_name
source_refresh_status
source_freshness_state
source_fresh
source_stale_module_count
source_missing_module_count
quality_blocking
expected_lag
context_only / audit_only
source_group_id
source_ids
missing_source_ids
```

## Implementation Plan

1. 复跑或读取最新 `/api/radar-runtime/modules/latest`、`/api/radar-runtime/cockpit/latest` 和 `reports/radar-runtime-audit-report.md`。
2. 对 6 个剩余模块逐个列出 stale / missing feature、source_id、freshness reason、是否 quality_blocking。
3. 修复 source group mapping、feature source metadata 或 freshness 分类口径。
4. 对慢变量应用 expected-lag / business-calendar-aware 规则，避免 context-only 数据误阻塞 runtime source freshness。
5. 复跑 Radar Runtime run-once 和审计报告。

## DoD

- `/api/radar-runtime/modules/latest` 中 14/14 modules 有明确 source freshness 结论。
- `source_missing_module_count = 0`，或剩余项均有 `configured_but_missing_source_id` 审计解释且不误判 blocking。
- `source_stale_module_count = 0`，或剩余 stale 仅为 expected_lag / context_only / audit_only 且不导致 BTC runtime cockpit 强结论。
- `asia_risk` 不再因可刷新 source 映射缺失而 stale。
- 审计报告列出修复前后对比。
- 后端相关测试通过。

## Test Plan

```text
python -m pytest backend/tests/test_radar_runtime*.py
python -m pytest backend/tests/test_api.py
npm run build
Invoke-RestMethod http://127.0.0.1:8118/api/radar-runtime/modules/latest
Invoke-RestMethod http://127.0.0.1:8118/api/radar-runtime/cockpit/latest
```

## Risks / Notes

- 慢变量不能按分钟级 fresh 判断；FRED、ETF、onchain slow proxies、options slow context 应按业务日历或 expected_lag 归类。
- 如果某个 source 真正不可用，应降级 participation，而不是伪造 fresh。
- 本任务完成后再启动 BTC 4H/1D Direct Trend 主线，避免新主线建立在不可信 runtime freshness 上。

## Execution Record

- Confirmed the previous P9-C54 blockers are closed in the current runtime snapshot:
  - `source_stale_module_count = 0`
  - `source_missing_module_count = 0`
  - `source_stale_modules = []`
  - `source_missing_modules = []`
- Confirmed overall runtime health:
  - `health_state = healthy`
  - `runtime_fresh = true`
  - `source_fresh = true`
  - `source_freshness_state = expected_lag`
- Added top-level runtime module API projection fields:
  - `source_freshness_state`
  - `source_blocking_feature_count`
  - `source_expired_feature_count`
  - `source_stale_feature_count`
  - `source_missing_feature_count`
  - `source_expected_lag_feature_count`
  - `source_context_only_stale_count`
- Verified the remaining non-fresh modules are expected-lag / partial live slow-source cases, not blocking stale or missing source cases.
- Refreshed `reports/radar-runtime-audit-report.md` and `.html` with `overall_status = PASS`.

## Verification

```text
python -m pytest backend/tests/test_radar_runtime_daemon.py
11 passed

python -m pytest backend/tests/test_api.py
4 passed

GET /api/radar-runtime/cockpit/latest
source_fresh=true
source_freshness_state=expected_lag
source_stale_module_count=0
source_missing_module_count=0

GET /api/radar-runtime/modules/latest
modules expose top-level source_freshness_state and source freshness counters.
```
