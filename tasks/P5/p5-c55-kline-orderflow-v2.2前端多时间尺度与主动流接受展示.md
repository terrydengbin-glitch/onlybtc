# P5-C55 / Kline Orderflow v2.2 前端多时间尺度与主动流接受展示

## 状态

DONE

## Phase

P5 Vue3 前端展示层

## 背景

`kline_orderflow v2.2` 前端需要从旧版单分数展示，升级为多区块展示：趋势敏感度、趋势可靠性、主动流接受度、VWAP/range 关键位、反证状态和波动率 regime。

## 推荐区块

```text
1. Signal Stage
   signal_stage
   kline_orderflow_state
   btc_implication
   volatility_regime

2. Trend Scores
   trend_sensitivity_score
   trend_reliability_score
   confidence_score

3. Flow Acceptance
   aggressor_flow_score
   flow_price_acceptance_score
   residual_confirmation_score
   absorption / exhaustion flags

4. VWAP & Range
   vwap_15m
   vwap_1h
   vwap_4h
   micro/local/major range
   false_breakout_score
   false_breakdown_score

5. Drivers & Invalidation
   support_drivers
   pressure_drivers
   conflict_drivers
   rejection_flags
   invalidation_conditions
```

## UI 语义规则

```text
early_warning:
  视觉上显示为预警，不显示为确认趋势

confirmed_signal:
  必须同时展示 reliability score 和确认 drivers

shock_vol:
  显示高波动降权/提高门槛提示

taker flow:
  展示为主动流接受/拒绝，不展示为直接多空
```

## DoD

- [ ] Radar Detail 可展示 v2.2 多区块。
- [ ] 缺失字段时 UI 稳定显示空态，不崩溃。
- [ ] 前端不把 early_warning 当 confirmed。
- [ ] 前端不把 taker buy/sell ratio 单独显示为方向结论。
- [ ] `npm run build` 通过。

## 关联任务

- P9-C34
- P4.5-C38
