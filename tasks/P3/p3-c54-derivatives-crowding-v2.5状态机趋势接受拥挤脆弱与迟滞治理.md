# P3-C54 / Derivatives Crowding v2.5 状态机、趋势接受、拥挤脆弱与迟滞治理

## 状态

DONE

## Phase

P3 算法、事件窗口与评分层

## 背景

`derivatives_crowding v2.5` 要从衍生品拥挤判断器升级为 BTC 趋势是否被杠杆市场接受的确认器。判断顺序必须变成：trend_prior -> derivatives signal -> BTC response -> standardized residual -> hysteresis。

## 输出契约

```json
{
  "module": "derivatives_crowding",
  "version": "p3.c60.derivatives_crowding.v2.5",
  "module_direction": "bullish|bearish|neutral",
  "module_score": 0,
  "confidence_score": 0,
  "signal_stage": "none|early_warning|fast_signal|confirmed_signal|conflict",
  "derivatives_state": "derivatives_accepted_uptrend|uptrend_long_crowding_fragility|uptrend_crowding_failure|short_building_confirms_downtrend|short_squeeze_setup|short_squeeze_confirmed|short_squeeze_exhaustion|forced_selling_followthrough|forced_selling_absorbed|leverage_reset|derivatives_neutral",
  "btc_implication": "trend_confirmed|trend_fragile|trend_rejected|squeeze_setup|squeeze_confirmed|squeeze_exhausting|liquidation_followthrough|forced_selling_absorbed|neutral",
  "trend_prior": {},
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

## 状态机

```text
derivatives_accepted_uptrend
uptrend_long_crowding_fragility
uptrend_crowding_failure
short_building_confirms_downtrend
short_squeeze_setup
short_squeeze_confirmed
short_squeeze_exhaustion
forced_selling_followthrough
forced_selling_absorbed
leverage_reset
derivatives_neutral
```

## 分数

```text
trend_acceptance_score: -100..+100
crowding_fragility_score: 0..100
squeeze_risk_score: -100..+100

module_score =
  0.35 * btc_acceptance_score
+ 0.20 * oi_participation_score
+ 0.15 * funding_basis_score
+ 0.15 * liquidation_response_score
+ 0.10 * positioning_skew_score
+ 0.05 * trend_prior_alignment_score
- data_quality_penalty
```

## Hysteresis

```text
confirmed_state_min_hold_hours = 2
early_warning_max_hold_hours = 6
state_flip_cooldown_minutes = 30
```

## DoD

- [ ] 输出 `semantic_profile_version = p3.c60.derivatives_crowding.v2.5`。
- [ ] 输出 `trend_acceptance_score`、`crowding_fragility_score`、`squeeze_risk_score`。
- [ ] Confirmed bullish 必须有 BTC response positive + residual positive + trend_prior 支持或 transition 上破。
- [ ] Confirmed bearish 必须有 BTC response negative + residual negative + trend_prior 不冲突。
- [ ] `trend_prior_confidence < 50` 时不允许 confirmed_signal。
- [ ] `volatility_regime == shock` 时提高确认门槛。
- [ ] liquidation 区分 follow-through / absorbed。
- [ ] 状态翻转有 cooldown / hysteresis。
- [ ] 单因子 funding/OI/long-short/liquidation spike 测试全部通过。

## 依赖

- P1-C56
- P2-C39
- P8-C31
- P9-C36
- P4.5-C40
- P5-C57
