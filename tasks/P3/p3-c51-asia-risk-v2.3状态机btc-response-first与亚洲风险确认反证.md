# P3-C51 / Asia Risk v2.3 状态机 BTC response first 与亚洲风险确认反证

## 状态

DONE

## Phase

P3 算法、状态机与评分层

## 背景

`asia_risk` v2.3 的方向语义必须收口：亚洲风险变量只产生 pressure / support / warning，BTC 亚洲时段 response、VWAP/range 结构和 residual 才决定最终方向。这样可以避免把 USDJPY、USDCNH、港股或 Korea premium 单因子误读为 BTC 多空。

## 目标

新增 `semantic_profile_version=p3.c56.asia_risk.v2.3`，输出完整结构化 profile：

```text
module_direction
module_score_signed
confidence_score
signal_stage
asia_risk_state
btc_implication
scores
btc_response
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
risk_off_pressure_score =
  0.35 * jpy_carry_unwind_pressure
+ 0.30 * cnh_devaluation_pressure
+ 0.20 * asia_equity_downside_pressure
+ 0.15 * asia_liquidity_stress_score
```

```text
asia_session_trend_score =
  0.35 * asia_session_btc_return_8h_z
+ 0.25 * asia_session_vwap_distance_z
+ 0.20 * asia_session_range_position_score
+ 0.20 * asia_session_volume_confirm_score
```

```text
regional_demand_score =
  0.40 * korea_premium_adjusted_score
+ 0.35 * hk_btc_etf_flow_score
+ 0.25 * asia_volume_participation_score
```

```text
btc_response_score =
  0.45 * asia_risk_residual_z_90d
+ 0.30 * asia_session_trend_score
+ 0.25 * downside_or_upside_break_confirm_score
```

```text
module_score_signed =
  0.55 * btc_response_score
+ 0.25 * asia_session_trend_score
+ 0.15 * regional_demand_score
- 0.05 * unconfirmed_risk_off_pressure
- data_quality_penalty_signed
```

## 方向映射

```text
module_score_signed >= +25:
  module_direction = bullish

module_score_signed <= -25:
  module_direction = bearish

otherwise:
  module_direction = neutral
```

## 状态机

```text
asia_risk_neutral
jpy_carry_unwind_warning
jpy_carry_unwind_confirmed
cnh_pressure_warning
asia_risk_off_confirmed
btc_resisting_asia_risk
btc_rejecting_asia_tailwind
asia_crypto_demand_support
kimchi_premium_stress
```

### JPY Carry Unwind Warning

```text
jpy_carry_unwind_pressure >= 60
and btc_response_score > -30
```

输出：

```text
module_direction = neutral
signal_stage = early_warning
btc_implication = trend_fragile
```

### JPY Carry Unwind Confirmed

```text
jpy_carry_unwind_pressure >= 70
and asia_session_btc_return_8h_z <= -0.8
and asia_risk_residual_z_90d <= -1.0
and asia_session_low_break_flag == true
```

输出：

```text
module_direction = bearish
signal_stage = confirmed_signal
btc_implication = risk_off_confirmed
```

### BTC Resisting Asia Risk

```text
risk_off_pressure_score >= 60
and asia_session_btc_return_8h_z >= 0
and asia_risk_residual_z_90d >= 1.0
and asia_session_range_position >= 0.6
```

输出：

```text
module_direction = neutral_to_mild_bullish
signal_stage = conflict
btc_implication = internal_strength
```

### BTC Rejecting Asia Tailwind

```text
regional_demand_score >= 40
and risk_off_pressure_score <= 40
and asia_session_btc_return_8h_z <= -0.5
and asia_risk_residual_z_90d <= -1.0
```

输出：

```text
module_direction = bearish
signal_stage = fast_signal
btc_implication = internal_weakness
```

### Asia Crypto Demand Support

```text
korea_premium_state == healthy_premium
and hk_btc_etf_flow_5d_z >= 0
and asia_session_btc_return_8h_z >= 0.5
and asia_session_btc_volume_z_30d >= 0.5
```

输出：

```text
module_direction = mild_bullish
signal_stage = fast_signal
btc_implication = regional_demand_support
```

### Kimchi Premium Stress

```text
korea_premium_state in ["fomo_premium", "stress_premium"]
and asia_session_btc_realized_vol_z >= 1.5
```

输出：

```text
module_direction = neutral_to_mild_bearish
signal_stage = early_warning
btc_implication = trend_fragile
```

## 输出契约

```json
{
  "module": "asia_risk",
  "version": "p3.c56.asia_risk.v2.3",
  "module_direction": "bullish|bearish|neutral",
  "module_score_signed": 0,
  "confidence_score": 0,
  "signal_stage": "none|early_warning|fast_signal|confirmed_signal|conflict",
  "asia_risk_state": "asia_risk_neutral|jpy_carry_unwind_warning|jpy_carry_unwind_confirmed|cnh_pressure_warning|asia_risk_off_confirmed|btc_resisting_asia_risk|btc_rejecting_asia_tailwind|asia_crypto_demand_support|kimchi_premium_stress",
  "btc_implication": "trend_confirmed|trend_fragile|risk_off_confirmed|internal_strength|internal_weakness|regional_demand_support|neutral",
  "scores": {},
  "btc_response": {},
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

- [ ] `semantic_profile_version=p3.c56.asia_risk.v2.3` 可输出。
- [ ] `risk_off_pressure_score` 高不直接导致 bearish。
- [ ] confirmed bearish 必须包含亚洲风险压力、BTC 亚洲时段下跌、negative residual、session low/VWAP 结构破位。
- [ ] confirmed bullish 必须包含 BTC 亚洲时段走强、positive residual、premium/ETF/volume 至少一项需求确认。
- [ ] Korea premium 拆分为 healthy/fomo/stress/collapsing/neutral/missing。
- [ ] 没有 BTC kline / BTC response 时，模块只能 neutral。
- [ ] 输出包含 invalidation_conditions。
- [ ] P3 pipeline 和相关单元测试通过。

## 关联任务

- P1-C53
- P2-C36
- P8-C28
- P9-C33
