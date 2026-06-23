# P3-C48 / Fund Flow v2.2 状态机 fast warning、confirmation 与 rejection

## 状态

DONE

## Phase

P3 算法、事件窗口与评分层

## 背景

`fund_flow` 当前已有 `fund_flow_absolute_direction`、`fund_flow_marginal_direction`、`fund_flow_state` 等字段，但仍偏向“资金流加权评分”。v2.2 要升级为：

```text
Fund Flow Confirmation / Rejection Module
```

核心不是“资金流好不好”，而是“资金流变化后 BTC 有没有接受、拒绝或抵抗”。

## 目标

新增 `p3.c50.fund_flow.v2.2` semantic profile，输出 ETF、稳定币、交易所供给与 BTC response 的三层状态机：

```text
fast_warning:
  资金流异常先出现，不要求 BTC 已经跌/涨。

confirmation:
  价格、供给、持续性与 residual 同向，确认趋势。

rejection:
  资金流看多但 BTC 不涨，或资金流看空但 BTC 不跌。
```

## 状态机

```text
etf_demand_accelerating
etf_demand_confirmed
etf_demand_fading
etf_outflow_warning
etf_outflow_confirmed
stablecoin_liquidity_tailwind
stablecoin_liquidity_drain
supply_squeeze_support
exchange_supply_pressure
exchange_flow_untrusted
btc_accepting_flow_tailwind
btc_rejecting_flow_tailwind
btc_resisting_flow_headwind
fund_flow_neutral
```

## 关键规则

### ETF Demand Accelerating

```text
etf_flow_1d_z_60d >= 1
or etf_flow_acceleration_3d > 0
or etf_inflow_streak_days >= 2

and btc_return_4h >= 0 or btc_return_24h >= 0
```

输出：

```text
direction = mild_bullish
btc_implication = early_institutional_demand
confidence = medium
```

### ETF Demand Confirmed

```text
etf_flow_3d_usd > 0
and etf_flow_7d_usd > 0
and etf_flow_7d_z_60d >= 0.75
and etf_inflow_streak_days >= 3
and btc_return_24h > 0
and fund_flow_residual_z_60d >= 0
```

输出：

```text
direction = bullish
btc_implication = trend_confirmed
confidence = high
```

### ETF Demand Fading

```text
etf_flow_7d_usd > 0
and etf_flow_acceleration_3d < 0
and etf_flow_1d_z_60d <= -0.5
```

输出：

```text
direction = neutral_to_mild_bearish
btc_implication = bullish_momentum_fading
confidence = medium
```

### ETF Outflow Warning

```text
etf_flow_1d_z_60d <= -1
or etf_outflow_streak_days >= 2
or etf_flow_reversal_2d == true

and btc_return_24h >= -0.5%
```

输出：

```text
direction = neutral_to_mild_bearish
btc_implication = trend_fragile
confidence = medium
```

### ETF Outflow Confirmed

```text
etf_flow_3d_usd < 0
and etf_flow_7d_usd < 0
and etf_outflow_streak_days >= 3
and btc_return_24h < 0
and fund_flow_residual_z_60d < 0
```

输出：

```text
direction = bearish
btc_implication = institutional_demand_drag
confidence = high
```

### Stablecoin Liquidity Tailwind

```text
stablecoin_mcap_change_7d > 0
and stablecoin_mcap_change_30d > 0
and ssr_z_180d <= 0
and btc_return_3d >= 0
```

输出：

```text
direction = mild_bullish
btc_implication = liquidity_support
confidence = medium
```

### Stablecoin Liquidity Drain

```text
stablecoin_mcap_change_7d < 0
and stablecoin_mcap_change_30d <= 0
and ssr_z_180d > 0
```

输出：

```text
direction = mild_bearish
btc_implication = liquidity_drain
confidence = medium
```

### Supply Squeeze Support

```text
btc_exchange_netflow_7d < 0
and btc_exchange_netflow_z_60d <= -1
and large_single_transfer_flag == false
and etf_flow_3d_usd >= 0
and btc_return_24h >= 0
```

输出：

```text
direction = mild_bullish
btc_implication = tradable_supply_tight
confidence = medium_to_high
```

### Exchange Supply Pressure

```text
btc_exchange_netflow_1d > 0
and btc_exchange_netflow_z_60d >= 1.5
and btc_return_24h <= 0
and large_single_transfer_flag == false
```

输出：

```text
direction = bearish
btc_implication = spot_supply_pressure
confidence = medium_to_high
```

### Exchange Flow Untrusted

```text
abs(btc_exchange_netflow_z_60d) >= 2
and large_single_transfer_flag == true
```

输出：

```text
direction = neutral
btc_implication = data_quality_warning
confidence_adjustment = -10
early_warning_flags += ["possible_exchange_internal_transfer"]
```

### BTC Rejecting Flow Tailwind

```text
etf_flow_3d_usd > 0
or stablecoin_mcap_change_7d > 0

and btc_return_24h <= 0
and fund_flow_residual_z_60d <= -1
```

输出：

```text
direction = bearish
btc_implication = internal_weakness
confidence = high
```

### BTC Resisting Flow Headwind

```text
etf_flow_3d_usd < 0
or btc_exchange_netflow_z_60d >= 1

and btc_return_24h >= 0
and fund_flow_residual_z_60d >= 1
```

输出：

```text
direction = bullish
btc_implication = internal_strength
confidence = high
```

## 打分结构

```json
{
  "etf_demand_score": 0,
  "stablecoin_liquidity_score": 0,
  "exchange_supply_score": 0,
  "btc_response_score": 0,
  "data_quality_penalty": 0,
  "module_score": 0
}
```

默认权重：

```text
0.40 * etf_demand_score
+ 0.20 * stablecoin_liquidity_score
+ 0.20 * exchange_supply_score
+ 0.20 * btc_response_score
- data_quality_penalty
```

fast mode：

```text
0.45 * etf_demand_score
+ 0.15 * stablecoin_liquidity_score
+ 0.15 * exchange_supply_score
+ 0.25 * btc_response_score
```

## 输出契约

```json
{
  "module": "fund_flow",
  "version": "p3.c50.fund_flow.v2.2",
  "module_direction": "bullish|bearish|neutral",
  "module_score": 0,
  "confidence_score": 0,
  "fund_flow_state": "etf_demand_accelerating|etf_demand_confirmed|etf_demand_fading|etf_outflow_warning|etf_outflow_confirmed|stablecoin_liquidity_tailwind|stablecoin_liquidity_drain|supply_squeeze_support|exchange_supply_pressure|exchange_flow_untrusted|btc_accepting_flow_tailwind|btc_rejecting_flow_tailwind|btc_resisting_flow_headwind|fund_flow_neutral",
  "btc_implication": "trend_confirmed|early_warning|trend_fragile|institutional_demand_drag|liquidity_support|liquidity_drain|tradable_supply_tight|spot_supply_pressure|internal_strength|internal_weakness|neutral",
  "scores": {},
  "states": {
    "etf_demand": {},
    "stablecoin_liquidity": {},
    "exchange_supply": {},
    "btc_response_confirmation": {}
  },
  "support_drivers": [],
  "pressure_drivers": [],
  "early_warning_flags": [],
  "data_quality_flags": []
}
```

## DoD

- [ ] 输出 `semantic_profile_version=p3.c50.fund_flow.v2.2`。
- [ ] 状态机覆盖 fast warning / confirmation / rejection。
- [ ] ETF outflow warning 不要求 BTC 已经明显下跌。
- [ ] `btc_rejecting_flow_tailwind` 和 `btc_resisting_flow_headwind` 能覆盖反证场景。
- [ ] 交易所内部转账风险触发 `exchange_flow_untrusted` 并降权。
- [ ] 稳定币只输出 liquidity regime，不直接强多空。
- [ ] P3 审计报告展示四个子状态与 scores。

## 关联任务

- P1-C50
- P2-C33
- P4.5-C34
- P9-C30
