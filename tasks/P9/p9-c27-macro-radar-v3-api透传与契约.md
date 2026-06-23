# P9-C27 / Macro Radar v3 API 透传与契约

## 状态

DONE

## 目标

让 FastAPI 聚合层完整透传 `macro_radar.v3` 的结构化语义，供 Dashboard、Radar Detail、History Replay 消费。

## 范围

API 需要透传：

```text
module_purpose
macro_trend_state
btc_implication
equity_beta
rates_pressure
dollar_pressure
volatility_stress
financial_stress
commodity_context
macro_impulse
btc_relative_confirmation
event_window
risk_score
confidence_adjustment
support_drivers
pressure_drivers
risk_drivers
invalidation_conditions
context_notes
```

## 契约要求

- `/api/p45/radar-modules/macro_radar` 返回 v3 子结构。
- Dashboard module node 优先读取 `macro_trend_state`。
- Radar Detail 可以读取八区块展示数据。
- 缺少 v3 payload 时 fallback 到旧字段，不返回 500。

## DoD

- API response 中 `macro_radar` 包含 `version=p3.c45.macro_radar.v3` 或兼容 fallback。
- risk/confidence 字段不被误写进 `module_direction`。
- support/pressure/risk/context drivers 保持数组结构，前端可直接消费。
- FastAPI 测试覆盖 v3 payload 和旧 payload fallback。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
.\.venv\Scripts\python.exe -m compileall -q backend/src/onlybtc
```
