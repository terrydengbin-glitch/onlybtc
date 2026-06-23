# P2-C25 / Trade Structure Flow 指标角色、权重与语义边界治理

## 状态

DONE

## 背景

`trade_structure_flow` 当前仍偏向“主动买卖 + mempool + liquidation 简单方向加总”。最新样本中，`taker_buy_sell_ratio` 很强时容易把模块显示为 `bullish`，但稳定币购买力、mempool 执行摩擦、清算状态并未确认趋势。

本模块应从“方向模块”升级为“短线交易结构状态模块”的上游指标契约。

## 目标

在 P2 层调整指标角色和权重边界：

1. `taker_buy_sell_ratio` 代表主动成交压力，不单独确认趋势。
2. `mempool_*` 默认作为 execution friction / risk context，不直接贡献 bullish / bearish。
3. `stablecoin_buying_power_proxy` 只表达 liquidity support / pressure，不单独决定 24h 方向。
4. `liquidation_long_usd` / `liquidation_short_usd` 标记为 liquidation event state，等待 P3 结合价格响应解读。
5. `futures_basis` 降权或迁移到 `derivatives_crowding`，避免 trade_structure_flow 与 derivatives 语义重复。

## 建议角色

```text
taker_buy_sell_ratio          -> aggressive_flow
exchange_spot_volume          -> volume_efficiency_context
liquidation_long_usd          -> liquidation_event
liquidation_short_usd         -> liquidation_event
stablecoin_buying_power_proxy -> liquidity_context
mempool_vsize_mb              -> execution_friction
mempool_tx_count              -> execution_friction
mempool_blocks_to_clear       -> execution_friction
mempool_min_fee_rate_sat_vb   -> execution_friction
futures_basis                 -> derivatives_pricing_context / migrate_candidate
```

## 权重建议

方向结构分只保留：

```text
aggressive_flow        0.40
price_response         0.30  # P3 计算，不在 P2 直接落分
liquidation_flow       0.20
volume_efficiency      0.10
```

背景修正项：

```text
stablecoin_liquidity   context modifier only
mempool_pressure       confidence/risk modifier only
futures_basis          migrate to derivatives_crowding or strong downweight
```

## 不改范围

- 不新增 P1 数据源。
- 不改变原始 source_id。
- 不直接在 P2 做完整状态机。
- 不删除现有字段，兼容旧 pipeline。

## DoD

- `mempool_*` 不再作为直接方向主驱动。
- `stablecoin_buying_power_proxy` 不再单独触发 `bullish_confirmation`。
- `taker_buy_sell_ratio` 标记为 aggressive flow，而不是完整趋势确认。
- liquidation 指标带有 `liquidation_event` 角色和 snapshot 数据边界说明。
- P3 能读取 P2 的角色字段完成复合语义治理。

## 验收

当 `taker_buy_sell_ratio > 1.30`，但无价格响应确认时，P2 不应把模块预设为强 bullish；P3 应能输出 `buy_pressure_unconfirmed` 或 `absorption_or_trapped_long`。

## Execution Notes

- `trade_structure_flow` 已调整为短线交易结构状态模块的上游契约。
- `taker_buy_sell_ratio` 角色改为 `aggressive_flow`，保留方向压力输入，但不再代表完整趋势确认。
- P1-C42 新增的 5m / 15m price response 指标已挂入 `trade_structure_flow`，角色为 `price_response`，当前 `affects_signal=false`，交给 P3-C37 / P3-C38 做组合确认。
- `mempool_*` 统一改为 `execution_friction`，`affects_signal=false`，只影响 confidence / risk flags。
- `stablecoin_buying_power_proxy` 改为 `liquidity_context`，`affects_signal=false`。
- `liquidation_long_usd` / `liquidation_short_usd` 改为 `liquidation_event`，`affects_signal=false`，等待 P3 结合价格响应解释。
- `futures_basis` 改为 `derivatives_pricing_context`，`affects_signal=false`，避免与 `derivatives_crowding` 重复推方向。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_radars.py -q
```

结果：`8 passed`。
