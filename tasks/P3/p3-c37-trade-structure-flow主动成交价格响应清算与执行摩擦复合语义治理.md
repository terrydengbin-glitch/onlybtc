# P3-C37 / Trade Structure Flow 主动成交、价格响应、清算与执行摩擦复合语义治理

## 状态

DONE

## 背景

当前 `trade_structure_flow` 已拆出浅层 profile：

```text
aggressive_flow_state
stablecoin_buying_power_state
liquidation_flow_state
mempool_pressure_state
```

但仍存在两个问题：

1. `taker_buy_sell_ratio` 强时容易把模块拉成 `bullish`。
2. 没有 `price_response` 层，无法判断主动买盘是否被价格接受。

本任务将 `trade_structure_flow` 升级为短线交易结构复合状态模块。

## 目标

输出完整复合语义：

```json
{
  "aggressive_flow_state": "strong_buying_pressure",
  "price_response_state": "need_kline_confirmation",
  "liquidation_state": "quiet",
  "mempool_pressure_state": "execution_friction",
  "stablecoin_liquidity_state": "liquidity_pressure",
  "trade_structure_state": "buy_pressure_unconfirmed",
  "module_effective_bias": "mild_support",
  "confirmation_state": "unconfirmed",
  "risk_state": "execution_friction"
}
```

## 核心规则

### Taker Buy/Sell Ratio

```text
0.97 - 1.03     neutral
1.03 - 1.12     mild_buy_pressure
1.12 - 1.30     buying_pressure
> 1.30          strong_buying_pressure

0.88 - 0.97     mild_sell_pressure
0.70 - 0.88     selling_pressure
< 0.70          strong_selling_pressure
```

限制：

```text
taker_buy_sell_ratio > 1.30 and price_response not confirmed
  -> trade_structure_state = buy_pressure_unconfirmed
  -> confirmation_state = unconfirmed
  -> 不允许 bullish_confirmation

taker_buy_sell_ratio > 1.30 and price_return_5m <= 0
  -> trade_structure_state = absorption_or_trapped_long

taker_buy_sell_ratio < 0.70 and price_return_5m >= 0
  -> trade_structure_state = sell_absorption_or_trapped_short
```

### Price Response

尽量复用现有 Kline 派生指标；若缺少 5m/15m，第一版可退化使用 1h：

```text
btc_return_1h
btc_close_position_1h
btc_volume_zscore_1h
btc_candle_body_pct_1h
```

建议后续新增：

```text
price_return_5m
price_return_15m
close_position_5m
range_expansion_z
flow_price_efficiency
```

### Liquidation

```text
SELL liquidation + price down      -> long_flush / long_flush_panic_risk
BUY liquidation + price up         -> short_squeeze / short_squeeze_chase_risk
SELL liquidation high + price back -> long_flush_absorbed
BUY liquidation high + price fail  -> squeeze_failed
quiet liquidation                  -> no_liquidation_confirmation
```

必须输出：

```json
{
  "liquidation_data_quality": "snapshot_not_full_market_volume"
}
```

### Mempool

```text
blocks_to_clear <= 2 -> normal_context
fee_rate_z > 2 or vsize_z > 2 -> execution_friction
fee_rate_z > 3 and blocks_to_clear > 6 -> extreme_execution_risk
```

原则：

```text
低拥堵不是 bullish。
高拥堵也不是 bearish。
mempool 只影响执行摩擦和 confidence_delta。
```

### Stablecoin

```text
stablecoin_buying_power_7d_z > 1  -> liquidity_support
stablecoin_buying_power_7d_z < -1 -> liquidity_pressure
otherwise                         -> neutral_liquidity
```

限制：

```text
stablecoin_liquidity_state 不能单独触发 bullish_confirmation。
liquidity_pressure 时，bullish effective score 应有上限，confirmation_state 最高 weak_confirmed。
```

## 状态枚举

```text
bullish_confirmation
bearish_confirmation
buy_pressure_unconfirmed
sell_pressure_unconfirmed
absorption_or_trapped_long
sell_absorption_or_trapped_short
short_squeeze_chase_risk
long_flush_panic_risk
long_flush_absorbed
squeeze_failed
mixed_structure
quiet_structure
```

## DoD

- `taker_buy_sell_ratio > 1.30` 但 Kline/price response 不确认时，不得输出 `bullish_confirmation`。
- mempool 指标默认只影响 `mempool_pressure_state` 和 `confidence_delta`。
- liquidation 必须结合 price response，不允许单项线性加分。
- stablecoin 只输出 liquidity 背景，不单独决定 24h 方向。
- 本轮类似数据必须输出 `trade_structure_state=buy_pressure_unconfirmed`、`module_effective_bias=mild_support`、`confirmation_state=unconfirmed`。
- P3 单元测试覆盖强买未确认、强买被吸收、强卖未确认、long flush、short squeeze、mempool friction、stablecoin pressure。

## 验收样本

```json
{
  "taker_buy_sell_ratio": 1.3391,
  "stablecoin_buying_power_proxy": "bearish",
  "liquidation_state": "quiet",
  "mempool_pressure": "elevated"
}
```

期望：

```json
{
  "trade_structure_state": "buy_pressure_unconfirmed",
  "module_effective_bias": "mild_support",
  "confirmation_state": "unconfirmed"
}
```

## Execution Notes

- `trade_structure_flow` 模块语义升级为 `p3.c37.trade_structure_flow.v1`。
- 新增并输出：
  - `aggressive_flow_state`
  - `price_response_state`
  - `liquidation_state`
  - `liquidation_data_quality`
  - `mempool_pressure_state`
  - `stablecoin_liquidity_state`
  - `trade_structure_state`
  - `module_effective_bias`
  - `confirmation_state`
  - `risk_state`
- `taker_buy_sell_ratio > 1.30` 且无 5m/15m/1h 价格响应确认时，输出 `buy_pressure_unconfirmed` / `unconfirmed`，不输出 `bullish_confirmation`。
- 主动买盘后价格不涨时输出 `absorption_or_trapped_long`；主动卖盘后价格不跌时输出 `sell_absorption_or_trapped_short`。
- 清算状态结合 price response 输出 `long_flush_panic_risk`、`short_squeeze_chase_risk`、`long_flush_absorbed`、`squeeze_failed` 等复合状态。
- mempool 只输出 execution friction / risk，不直接给 bullish 或 bearish。
- stablecoin 只输出 liquidity support / pressure / neutral，不单独确认趋势。

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_p3_pipeline.py -q
```

结果：`25 passed`。
