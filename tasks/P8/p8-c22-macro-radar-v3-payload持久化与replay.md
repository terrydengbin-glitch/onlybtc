# P8-C22 / Macro Radar v3 payload 持久化与 replay

## 状态

DONE

## 目标

保证 `macro_radar.v3` 结构化 payload 在 SQLite、final payload、history replay 中完整保留，支持后续审计与回放。

## 范围

持久化和 replay 需要覆盖：

```text
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
invalidation_conditions
context_notes
```

## DoD

- 最新 run 的 `macro_radar.v3` payload 可以从数据库读取。
- history replay 不丢失 v3 子结构。
- P4.5 与 P9 读取 replay payload 时不需要重新计算状态机。
- 旧版 `macro_radar` payload 可 fallback，不导致 API 500。
- source freshness 与 run_scope 字段在 replay 中可审计。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_storage.py backend\tests\test_p45_dashboard_api.py -q
.\.venv\Scripts\python.exe -m compileall -q backend/src/onlybtc
```
