# P9-C25 / Options Volatility v2.1 API 透传与契约

## 状态

DONE

## 背景

P3-C42 会为 `options_volatility` 输出风险结构化 payload。P9 需要保证 Dashboard、Radar Detail、Evidence、History Replay 能读取同一份结构，不把它降级成普通方向分。

## 目标

API 透传：

```text
module_purpose
options_short_term_state
risk_score
confidence_adjustment
trade_permission_hint
volatility_regime
protection_demand
tail_risk
expiry_pressure
pinning_structure
data_quality
risk_drivers
context_notes
```

## 契约要求

- `module_direction` 固定透传为 `neutral`。
- `module_score` / `module_effective_score` 固定透传为 `0`。
- 不生成 `support_drivers` / `pressure_drivers` 的方向解释。
- Radar Detail API 必须提供五区块展示所需字段。

## DoD

- `/api/p45/radar-modules/options_volatility` 返回 v2.1 结构。
- Dashboard 聚合 API 可消费 `risk_score`、`trade_permission_hint`。
- 缺失字段时兼容旧 run，不返回 500。
- API 测试通过。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
```
