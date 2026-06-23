# P9-C23 / Trade Structure Flow 复合语义 API 透传

## 状态

DONE

## 背景

P3-C37 / P4.5-C25 会新增 `trade_structure_flow` 的复合状态字段。FastAPI 需要稳定透传到 Dashboard、Radar Detail、Evidence Detail，避免前端只能看到旧的 `module_direction`。

## 目标

1. `/api/p45/dashboard` 透传 trade structure 摘要字段。
2. `/api/p45/radar-modules/trade_structure_flow` 透传完整复合字段。
3. Evidence detail 展示 taker / liquidation / mempool / stablecoin 的语义解释字段。
4. DTO 保持向后兼容，旧字段保留，新字段优先。

## API 字段

```json
{
  "trade_structure_state": "buy_pressure_unconfirmed",
  "aggressive_flow_state": "strong_buying_pressure",
  "price_response_state": "need_kline_confirmation",
  "liquidation_state": "quiet",
  "mempool_pressure_state": "execution_friction",
  "stablecoin_liquidity_state": "liquidity_pressure",
  "module_effective_bias": "mild_support",
  "confirmation_state": "unconfirmed",
  "risk_state": "execution_friction",
  "trade_structure_summary": "主动买盘强但价格响应未确认。"
}
```

## DoD

- Dashboard API 中 trade structure 节点可拿到 `trade_structure_state`。
- Radar Detail API 中模块卡和指标节点可拿到复合语义字段。
- Evidence Detail 中 taker / mempool / liquidation / stablecoin 的解释不再只有 `semantic.radar_rule`。
- API 测试覆盖字段透传和缺字段 fallback。
- 旧前端字段 `module_direction` 仍可用，但不作为优先展示字段。

## Execution Notes

- Dashboard API 的 `radar_modules` 已透传 `trade_structure_flow` 复合语义字段。
- Radar Detail API 已透传模块级字段和指标级 `price_response_*` 字段。
- Evidence Detail API 通过统一 metric evidence payload 透传：
  - `price_response_state`
  - `price_response_confidence`
  - `flow_price_efficiency_state`
  - `price_response_source`
- `_project_module` 新增 `trade_structure_summary`，用于前端优先展示复合状态文案。
- 旧字段 `module_direction` / `module_effective_direction` 保持兼容。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p45_dashboard_api.py -q
```

结果：`14 passed`。
