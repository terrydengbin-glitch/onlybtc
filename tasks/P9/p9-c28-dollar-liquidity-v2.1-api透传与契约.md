# P9-C28 / Dollar Liquidity v2.1 API 透传与契约

## 状态

DONE

## Execution Record

- DONE: FastAPI dashboard/detail projection exposes `dollar_liquidity_v21`.
- DONE: v2.1 profile direction/score/state override legacy fallback in API projection.
- Verified: target regression suite -> 124 passed.

## 背景

P9 API 需要把 `dollar_liquidity.v2.1` 的结构化字段透传给 Dashboard、Radar Detail 和历史回放页面。

## 目标

扩展 API 契约，保证前端可以稳定读取：

```text
dollar_liquidity_state
data_freshness
liquidity_level
liquidity_impulse
reserve_buffer
liquidity_drain_pressure
repo_funding_pressure
btc_response_confirmation
risk_score
confidence_adjustment
support_drivers
pressure_drivers
risk_drivers
context_notes
```

## DoD

- `/api/p45/radar-modules/dollar_liquidity` 返回 v2.1 payload。
- `/api/p45/dashboard/latest` 的 modules 列表保留 v2.1 display state。
- `/api/p45/evidence` 不把 raw `sofr` / `on_rrp` / `tga` 误展示成单因子方向 driver。
- API 对旧 run 保持兼容。
- contract 测试覆盖 latest、detail、replay。

## 验证建议

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
```
