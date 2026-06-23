# P5-C52 / Onchain Valuation v2.2 前端慢快分数、关键位与 Signal Stage 展示

## 状态

DONE

## Phase

P5 Dashboard 与可视化层

## 背景

`onchain_valuation.v2.2` 不再是单一方向分，而是输出慢变量 `regime_score`、快变量 `trend_delta_score`、动态 STH 成本位、`signal_stage`、proxy flags 与 invalidation conditions。前端需要避免把 early warning 或估值背景显示成强方向。

## 目标

在 Vue3 Radar Detail 中为 `onchain_valuation` 增加 v2.2 专属展示：

```text
Regime 背景
Trend Delta 趋势响应
Cost Basis Key Levels
SOPR / Realized Cap / BTC Response
Proxy / Data Quality
Invalidation Conditions
```

## 展示优先级

模块标签优先级：

```text
signal_stage
-> onchain_valuation_state
-> btc_implication
-> module_bias
-> module_direction
```

warning / fast_signal 使用观察或混合视觉，不使用纯 bullish/bearish 强色。

## 区块

### Regime

```text
module_bias
regime_score
mvrv_zscore
mvrv_ratio
nupl
realized_cap_trend_score
```

### Trend Delta

```text
signal_stage
trend_delta_score
btc_response_score
cost_basis_reaction_score
profit_realization_delta_score
realized_cap_impulse_score
```

### Key Levels

```text
realized_price
sth_cost_basis
sth_upper_band
sth_lower_band
lth_cost_basis
btc_vs_sth_cost_basis_pct
```

### Confirmation / Rejection

```text
sopr
sopr_z_90d
sopr_cross_1_direction
onchain_residual_z_90d
btc_implication
support_drivers
pressure_drivers
```

### Governance

```text
proxy_flags
data_quality_flags
early_warning_flags
invalidation_conditions
```

## DoD

- [ ] Radar Detail 展示 `onchain_valuation_v22` 或等价 v2.2 contract。
- [ ] 慢变量和快变量分区展示。
- [ ] 动态 STH 上下带和 key levels 可读。
- [ ] `signal_stage=early_warning` 不显示成 confirmed 方向。
- [ ] proxy flags 明确展示为低置信 context。
- [ ] invalidation conditions 展示完整。
- [ ] `npm run build` 通过。

## 关联任务

- P9-C31
- P4.5-C35
