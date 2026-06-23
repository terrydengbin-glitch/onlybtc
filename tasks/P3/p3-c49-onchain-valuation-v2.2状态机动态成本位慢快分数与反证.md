# P3-C49 / Onchain Valuation v2.2 状态机、动态成本位、慢快分数与反证

## 状态

DONE

## Phase

P3 算法、事件窗口与评分层

## 背景

`onchain_valuation` 要从“估值高低打分器”升级为“链上成本基础、盈亏兑现与 BTC response 的确认/反证模块”。v2.2 必须拆分慢变量和快变量：

```text
regime_score       = 链上估值大背景，适合 7d-90d
trend_delta_score  = 趋势变化响应，适合 4h-14d
```

`module_direction` 由 `trend_delta_score` 主导，`module_bias` 由 `regime_score` 主导。

## 目标

新增 `p3.c52.onchain_valuation.v2.2` semantic profile，并输出：

```text
signal_stage:
  none
  early_warning
  fast_signal
  confirmed_signal
  invalidated
```

## 状态机

```text
sth_retest_warning
sth_reclaim_fast
sth_reclaim_confirmed
sth_rejection_fast
sth_breakdown_confirmed
sopr_recovery_fast
sopr_recovery_confirmed
profit_taking_warning
sopr_loss_realization
realized_cap_inflow_confirmed
realized_cap_drain_warning
btc_accepting_onchain_tailwind
btc_rejecting_onchain_tailwind
btc_resisting_onchain_headwind
overheated_distribution_warning
euphoria_top_risk
onchain_neutral
```

## 关键规则

### STH Retest Warning

```text
abs(btc_vs_sth_cost_basis_pct) <= sth_band_pct
and btc_return_24h weakening
and onchain_residual_z_90d < -0.5
```

输出：

```text
signal_stage = early_warning
btc_implication = trend_fragile
```

### STH Reclaim Fast

```text
btc_price > upper_sth_band
and btc_return_24h > 0
and onchain_residual_z_90d > 0
```

输出：

```text
signal_stage = fast_signal
module_direction = bullish
btc_implication = trend_reclaim_attempt
```

### STH Reclaim Confirmed

```text
btc_price > upper_sth_band
and btc_close_2d_above_sth_band = true
and sopr >= 1
and realized_cap_impulse_z_180d >= 0
and onchain_residual_z_90d > 0
```

输出：

```text
signal_stage = confirmed_signal
module_direction = bullish
btc_implication = trend_reclaim
```

### STH Breakdown Confirmed

```text
btc_price < lower_sth_band
and btc_close_2d_below_sth_band = true
and sopr < 1
and sopr_below_1_streak_days >= 2
and onchain_residual_z_90d < -1
```

输出：

```text
signal_stage = confirmed_signal
module_direction = bearish
btc_implication = trend_breakdown
```

### BTC Rejecting Onchain Tailwind

```text
realized_cap_impulse_z_180d > 0
or valuation_regime_score > 0

but:
  btc_return_3d <= 0
  and onchain_residual_z_90d <= -1
  and btc_price below or failing near sth_cost_basis
```

输出：

```text
signal_stage = confirmed_signal
module_direction = bearish
btc_implication = internal_weakness
```

## 打分结构

```text
trend_delta_score =
  35% btc_response_score
+ 30% cost_basis_reaction_score
+ 20% profit_realization_delta_score
+ 15% realized_cap_impulse_score
```

```text
regime_score =
  35% valuation_regime_score
+ 25% realized_cap_trend_score
+ 20% lth_cost_basis_score
+ 10% miner_pressure_score
+ 10% whale_pressure_score
```

```text
module_score =
  70% trend_delta_score
+ 30% regime_score
- data_quality_penalty
```

强制反证：

```text
if valuation_regime_score bullish
but btc_response_score <= -40
and onchain_residual_z_90d <= -1:
  module_direction = bearish
  btc_implication = internal_weakness
```

## Hysteresis / Cooldown

```text
state_flip_cooldown_hours = 12
confirmed_state_min_hold_hours = 24
early_warning_max_hold_hours = 48
```

```text
if last_state = sth_reclaim_confirmed:
  only downgrade if:
    btc_price < sth_cost_basis
    and btc_close_1d_below_sth = true
    and onchain_residual_z_90d < 0

if last_state = sth_breakdown_confirmed:
  only upgrade if:
    btc_price > sth_cost_basis
    and btc_close_1d_above_sth = true
    and sopr >= 1
```

## 输出契约

```json
{
  "module": "onchain_valuation",
  "version": "p3.c52.onchain_valuation.v2.2",
  "module_direction": "bullish|bearish|neutral",
  "module_bias": "supportive|fragile|overheated|capitulation|neutral",
  "module_score": 0,
  "trend_delta_score": 0,
  "regime_score": 0,
  "confidence_score": 0,
  "signal_stage": "none|early_warning|fast_signal|confirmed_signal|invalidated",
  "onchain_valuation_state": "",
  "btc_implication": "",
  "scores": {},
  "key_levels": {},
  "support_drivers": [],
  "pressure_drivers": [],
  "early_warning_flags": [],
  "invalidation_conditions": [],
  "proxy_flags": [],
  "data_quality_flags": []
}
```

## DoD

- [ ] 输出 `semantic_profile_version=p3.c52.onchain_valuation.v2.2`。
- [ ] MVRV/NUPL 不允许单独触发 confirmed_signal。
- [ ] STH reclaim/rejection 使用动态 band。
- [ ] SOPR crossing 1 只能触发 fast_signal，不能直接 confirmed。
- [ ] confirmed_signal 至少需要 price response + onchain metric + residual 三类证据。
- [ ] tier_3 proxy 不允许触发 confirmed_signal。
- [ ] `module_score`、`trend_delta_score`、`regime_score` 分开输出。
- [ ] `signal_stage`、`invalidation_conditions` 必须输出。
- [ ] state flip 有 cooldown 与 hysteresis。
- [ ] P3 审计报告展示慢快分数、状态、关键位与 proxy flags。

## 关联任务

- P1-C51
- P2-C34
- P8-C26
- P9-C31
