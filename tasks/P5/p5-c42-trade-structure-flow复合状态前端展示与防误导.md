# P5-C42 / Trade Structure Flow 复合状态前端展示与防误导

## 状态

DONE

## 背景

当前 Dashboard / Radar Detail 容易把 `trade_structure_flow` 显示为 `bullish`，但业务上更准确的状态可能是：

```text
buy_pressure_unconfirmed
absorption_or_trapped_long
execution_friction
liquidity_pressure
```

前端需要优先展示复合状态，而不是旧方向标签。

## 目标

1. Dashboard trade_structure_flow 节点优先显示 `trade_structure_state`。
2. Radar Detail 中展示五个子状态：主动成交、价格响应、清算、mempool、稳定币。
3. 颜色映射避免把 `buy_pressure_unconfirmed` 显示成纯绿色 support。
4. 节点文案解释“主动买盘强但未确认”。

## UI 映射

```text
bullish_confirmation       -> support
bearish_confirmation       -> pressure
buy_pressure_unconfirmed   -> mixed / wait confirm
sell_pressure_unconfirmed  -> mixed / wait confirm
absorption_or_trapped_long -> pressure-easing / caution
short_squeeze_chase_risk   -> mixed / chase risk
long_flush_absorbed        -> mixed / absorption
execution_friction         -> data/risk badge
```

## 展示内容

模块卡：

```text
Trade Structure
状态：主动买盘强但未确认
主动成交：strong buying pressure
价格响应：need confirmation
清算：quiet
mempool：execution friction
稳定币：liquidity pressure
```

## DoD

- `trade_structure_state=buy_pressure_unconfirmed` 时，前端不得显示纯 bullish 主标签。
- Radar Detail 能看到 aggressive flow / price response / liquidation / mempool / stablecoin 五个子状态。
- Evidence 弹窗中 taker 不再解释为“单项决定 bullish”。
- 缺少新字段时 fallback 到旧 `trend_state`，再 fallback 到 `module_direction`。
- 视觉样式与现有 P5 深色 Dashboard 一致。

## Execution Notes

- `moduleDisplayState` 优先使用 `trade_structure_state`，再 fallback 到原有状态字段。
- `buy_pressure_unconfirmed` / `sell_pressure_unconfirmed` / `short_squeeze_chase_risk` 等状态映射为 mixed / wait-confirm 风格，避免纯 bullish 主标签。
- `moduleDisplayLabel` / `moduleDisplayShortLabel` 增加 trade structure 状态中文标签。
- Radar Detail 中新增 trade structure 五个子状态展示：
  - aggressive flow
  - price response
  - liquidation
  - mempool
  - stablecoin
- Radar metric panel 新增 `Price Response Confirmation` 区块，展示 `price_response_state`、`price_response_confidence`、`flow_price_efficiency_state`、`price_response_source`。
- `radarMetricSummary` 对 price response 指标显示“confirmation layer only”，避免把 taker / 5m 响应解释成单项趋势触发。

## Tests

```powershell
cd frontend
npm run build
```

结果：build passed。
