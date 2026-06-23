# P3-C50 / BTC Adoption v2.3 状态机 Fast/Core/Regime 与采用度确认反证

## 状态

DONE

## Phase

P3 算法、事件窗口与评分层

## 背景

`btc_adoption` v2.3 不负责单独预测 BTC 多空，而是判断链上采用度是否正在确认、削弱、提前预警或反证 BTC 当前趋势。模块必须拆成：

```text
fast_layer: 0h-24h
core_layer: 1d-7d
regime_layer: 14d-90d
```

这样既能捕捉 fee/mempool 与 BTC response 的快速变化，又不会被 active address、hashrate、Lightning 等慢变量误导。

## 目标

新增 `semantic_profile_version=p3.c54.btc_adoption.v2.3`，并输出：

```text
module_direction
module_score
confidence_score
signal_stage
btc_adoption_state
btc_implication
scores
states
support_drivers
pressure_drivers
conflict_drivers
early_warning_flags
data_quality_flags
proxy_flags
invalidation_conditions
```

## 打分结构

```text
fast_trend_score =
  40% btc_response_score
+ 25% fee_mempool_score
+ 20% short_activity_impulse_score
+ 15% short_settlement_impulse_score
```

```text
core_confirmation_score =
  35% settlement_demand_score
+ 25% activity_quality_score
+ 25% nvt_improvement_score
+ 15% price_acceptance_score
```

```text
regime_context_score =
  35% network_security_score
+ 25% l2_adoption_score
+ 25% miner_pressure_score
+ 15% network_health_score
```

```text
module_score =
  0.35 * fast_trend_score
+ 0.45 * core_confirmation_score
+ 0.20 * regime_context_score
- data_quality_penalty
```

## Signal Stage

```text
abs(module_score) < 15:
  signal_stage = none

15 <= abs(module_score) < 25:
  signal_stage = early_warning

25 <= abs(module_score) < 40:
  signal_stage = fast_signal

abs(module_score) >= 40 and core_confirmation_score 同向:
  signal_stage = confirmed_signal

fast_trend_score 与 core_confirmation_score 严重背离:
  signal_stage = conflict
  module_direction = neutral unless btc_response_score is extreme
```

## 状态机

```text
activity_expansion_confirmed
activity_spike_untrusted
settlement_demand_confirmed
settlement_demand_fading
healthy_fee_demand
mempool_congestion_risk
btc_accepting_adoption_tailwind
btc_rejecting_adoption_tailwind
btc_resisting_adoption_headwind
network_security_supportive
miner_security_pressure
l2_adoption_supportive
btc_adoption_neutral
```

### Activity Expansion Confirmed

```text
active_entities_or_addresses_z_60d >= 1.0
and transaction_count_z_60d >= 0.8
and transfer_volume_adjusted_usd_z_60d >= 0.5
and btc_return_24h >= 0
```

### Activity Spike Untrusted

```text
transaction_count_z_60d >= 2.0
and transfer_volume_adjusted_usd_z_60d <= 0
```

or

```text
tx_per_active_entity_z_60d >= 2.5
and fee_pressure_z_60d >= 1.5
```

### Settlement Demand Confirmed

```text
transfer_volume_adjusted_usd_z_60d >= 1.0
and nvt_proxy_change_7d < 0
and btc_return_24h >= 0
```

### Settlement Demand Fading

```text
transfer_volume_adjusted_usd_change_7d_pct < 0
and nvt_proxy_change_7d > 0
and btc_return_24h <= 0
```

### Healthy Fee Demand

```text
fee_pressure_z_60d >= 1.0
and transfer_volume_adjusted_usd_z_60d >= 0.5
and btc_return_24h >= 0
```

### Mempool Congestion Risk

```text
fee_pressure_z_60d >= 1.5
and mempool_vsize_z_30d >= 1.5
and transfer_volume_adjusted_usd_z_60d <= 0
and btc_return_24h <= 0
```

### BTC Accepting Adoption Tailwind

```text
settlement_demand_score >= 20
and activity_quality_score >= 10
and btc_return_24h > 0
and adoption_residual_z_90d >= 0
```

### BTC Rejecting Adoption Tailwind

```text
settlement_demand_score >= 20
or activity_quality_score >= 20

and btc_return_24h <= 0
and adoption_residual_z_90d <= -1
```

### BTC Resisting Adoption Headwind

```text
settlement_demand_score <= -20
or activity_quality_score <= -20

and btc_return_24h >= 0
and adoption_residual_z_90d >= 1
```

### Miner Security Pressure

```text
hashrate_14d_ma_change_7d_pct < -3%
and hashprice_z_90d <= -1
and miner_revenue_z_90d <= -1
```

## 输出契约

```json
{
  "module": "btc_adoption",
  "version": "p3.c54.btc_adoption.v2.3",
  "module_direction": "bullish|bearish|neutral",
  "module_score": 0,
  "confidence_score": 0,
  "timeframe": {
    "fast_layer": "0h-24h",
    "core_layer": "1d-7d",
    "regime_layer": "14d-90d"
  },
  "signal_stage": "none|early_warning|fast_signal|confirmed_signal|invalidated|conflict",
  "btc_adoption_state": "",
  "btc_implication": "",
  "scores": {},
  "states": {},
  "support_drivers": [],
  "pressure_drivers": [],
  "conflict_drivers": [],
  "early_warning_flags": [],
  "data_quality_flags": [],
  "proxy_flags": [],
  "invalidation_conditions": []
}
```

## DoD

- [ ] 输出 `semantic_profile_version=p3.c54.btc_adoption.v2.3`。
- [ ] active address、tx count、hashrate、Lightning level 不允许单独触发 confirmed_signal。
- [ ] confirmed_signal 至少包含 core_confirmation + btc_response。
- [ ] activity spike 但 adjusted transfer volume 不升时，必须降级为 `activity_spike_untrusted`。
- [ ] fee 高不能直接 bullish，必须结合 settlement 和 BTC response。
- [ ] hashrate/hashprice 只影响 regime_context，不直接拉 24h 方向。
- [ ] `adoption_residual_z_90d` 进入接受/拒绝状态机。
- [ ] fast/core 冲突时输出 `signal_stage=conflict`。
- [ ] 输出 invalidation_conditions。
- [ ] P3 单测、radar 聚合测试通过。

## 关联任务

- P1-C52
- P2-C35
- P8-C27
- P9-C32
- P4.5-C36
- P5-C53
