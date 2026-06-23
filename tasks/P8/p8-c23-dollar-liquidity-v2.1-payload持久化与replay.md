# P8-C23 / Dollar Liquidity v2.1 payload 持久化与 replay

## 状态

DONE

## Execution Record

- DONE: P3 scored module payload carries v2.1 layer contract for persistence/replay.
- DONE: final payload keeps `dollar_liquidity_explanation` and flattened module layer fields.
- Verified: target regression suite -> 124 passed.

## 背景

`dollar_liquidity.v2.1` 新增多层结构化 payload，需要保证 SQLite 持久化、历史回放和 replay API 不丢字段。

## 目标

确保以下字段可以持久化与回放：

```text
data_freshness
liquidity_level
liquidity_impulse
reserve_buffer
liquidity_drain_pressure
repo_funding_pressure
btc_response_confirmation
dollar_liquidity_state
risk_score
confidence_adjustment
support_drivers
pressure_drivers
risk_drivers
context_notes
```

## DoD

- 最新 run 的 `dollar_liquidity.v2.1` payload 能写入 SQLite。
- 历史 replay 能恢复完整 payload。
- replay 不因旧版 `dollar_liquidity` 缺少 v2.1 字段而报错。
- 历史旧 payload fallback 到 legacy display。
- 测试覆盖 latest 与 replay 两条路径。

## 验证建议

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py backend\tests\test_p45_final_writer.py -q
```
