# P3-C52 / Kline Orderflow v2.2 多时间尺度状态机、主动流接受与假突破反证

## 状态

DONE

## Phase

P3 算法、状态机与评分层

## 背景

`kline_orderflow v2.2` 的核心是把短线敏感度和趋势确认分开。主动买盘强不等于 BTC 看多；主动买盘强且价格接受，才看多。主动卖盘强也不等于 BTC 看空；主动卖盘强且价格继续被压低，才看空。

## 目标

新增 `semantic_profile_version=p3.c57.kline_orderflow.v2.2`，输出完整结构化 profile。

## 分数结构

```text
trend_sensitivity_score =
  0.25 * slope_acceleration_score
+ 0.25 * taker_flow_acceleration_score
+ 0.20 * vwap_reclaim_rejection_score
+ 0.15 * micro_range_break_score
+ 0.15 * residual_surprise_score
```

```text
trend_reliability_score =
  0.30 * price_structure_score
+ 0.25 * flow_price_acceptance_score
+ 0.20 * vwap_acceptance_score
+ 0.15 * volume_confirmation_score
+ 0.10 * residual_confirmation_score
- data_quality_penalty
- contradiction_penalty
```

## 状态机

```text
trend_up_confirmed
trend_down_confirmed
bullish_fast_shift
bearish_fast_shift
taker_buy_absorption
taker_sell_exhaustion
false_breakout_confirmed
false_breakdown_confirmed
vwap_reclaim_acceptance
vwap_rejection_pressure
range_chop
neutral
```

## 关键规则

```text
confirmed_signal:
  必须同时满足 price structure + flow acceptance + VWAP acceptance + residual not against

early_warning:
  可以使用 1m/5m/15m 快变量，但不能升级为 confirmed_signal

false_breakout / false_breakdown:
  优先级高于普通 breakout

shock_vol:
  禁止单独根据 5m/15m 输出 confirmed_signal
```

## 输出契约

```json
{
  "module": "kline_orderflow",
  "version": "p3.c57.kline_orderflow.v2.2",
  "module_direction": "bullish|bearish|mild_bullish|mild_bearish|neutral",
  "module_score": 0,
  "trend_sensitivity_score": 0,
  "trend_reliability_score": 0,
  "confidence_score": 0,
  "signal_stage": "none|early_warning|fast_signal|confirmed_signal|conflict",
  "volatility_regime": "low_vol|normal_vol|high_vol|shock_vol",
  "kline_orderflow_state": "trend_up_confirmed|trend_down_confirmed|bullish_fast_shift|bearish_fast_shift|taker_buy_absorption|taker_sell_exhaustion|false_breakout_confirmed|false_breakdown_confirmed|vwap_reclaim_acceptance|vwap_rejection_pressure|range_chop|neutral",
  "btc_implication": "upside_trend_confirmed|downside_trend_confirmed|upside_shift_attempt|downside_shift_attempt|buy_flow_absorbed|sell_pressure_exhausted|failed_upside_breakout|failed_downside_breakdown|neutral",
  "scores": {},
  "key_levels": {},
  "drivers": {},
  "invalidation_conditions": []
}
```

## DoD

- [ ] `semantic_profile_version=p3.c57.kline_orderflow.v2.2` 可输出。
- [ ] early_warning、fast_signal、confirmed_signal 语义隔离。
- [ ] confirmed_signal 必须同时满足 price structure、flow acceptance、VWAP acceptance、residual not against。
- [ ] false breakout / false breakdown 优先级高于普通 breakout。
- [ ] taker buy/sell 高不直接触发方向。
- [ ] high_vol / shock_vol 下提高确认门槛。
- [ ] kline stale 或 taker volume missing 时降级，不输出 confirmed_signal。
- [ ] P3 pipeline 和相关单元测试通过。

## 关联任务

- P1-C54
- P2-C37
- P8-C29
- P9-C34
