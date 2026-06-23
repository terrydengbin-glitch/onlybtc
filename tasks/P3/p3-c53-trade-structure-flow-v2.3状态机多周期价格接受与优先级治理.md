# P3-C53 / Trade Structure Flow v2.3 状态机、多周期价格接受与优先级治理

## 状态

DONE

## Phase

P3 算法、事件窗口与评分层

## 背景

`trade_structure_flow` 需要升级为 `p3.c58.trade_structure_flow.v2.3`。核心是用 5m/15m 的盘口变薄、spread 扩大、主动流突变和清算后反应提高敏感度，用 BTC price acceptance、spot/perp 质量拆分、标准化 residual 和状态优先级保证正确性。

## 目标

实现 v2.3 状态机与输出契约：

```text
structure_signal 发现压力
btc_response 确认方向
residual 发现背离
confirmed_signal 必须有 price acceptance
```

## 状态优先级

```text
P0 data_invalid
P1 liquidation_cascade_confirmed / forced_selling_absorbed / short_squeeze_confirmed
P2 downside_liquidity_breakdown_confirmed
P3 long_crowding_failure / squeeze_failed
P4 spot_led_trend_accepted
P5 perp_led_rally_fragile
P6 liquidity_breakdown_warning
P7 micro_turn_up_candidate / micro_turn_down_candidate
P8 neutral
```

## 状态机

```text
micro_turn_up_candidate
micro_turn_down_candidate
spot_led_trend_accepted
perp_led_rally_fragile
long_crowding_failure
liquidity_breakdown_warning
downside_liquidity_breakdown_confirmed
forced_selling_absorbed
liquidation_cascade_confirmed
short_squeeze_confirmed
squeeze_failed
trade_structure_neutral
```

## 输出契约

```json
{
  "module": "trade_structure_flow",
  "version": "p3.c58.trade_structure_flow.v2.3",
  "module_direction": "bullish|bearish|neutral",
  "module_score": 0,
  "confidence_score": 0,
  "signal_stage": "none|early_warning|fast_signal|confirmed_signal|conflict",
  "trade_structure_state": "",
  "btc_implication": "",
  "scores": {
    "price_acceptance_score": 0,
    "aggressive_flow_score": 0,
    "liquidity_directional_score": 0,
    "spot_perp_quality_score": 0,
    "leverage_structure_score": 0,
    "liquidation_response_score": 0,
    "residual_confirmation_score": 0,
    "data_quality_penalty": 0
  },
  "multi_horizon": {
    "5m": {"direction": "bullish|bearish|neutral", "score": 0, "price_acceptance": 0},
    "15m": {"direction": "bullish|bearish|neutral", "score": 0, "price_acceptance": 0},
    "1h": {"direction": "bullish|bearish|neutral", "score": 0, "price_acceptance": 0}
  },
  "states": {
    "liquidity": {},
    "aggressive_flow": {},
    "spot_perp_lead": {},
    "leverage": {},
    "liquidation": {},
    "btc_response": {},
    "residual": {}
  },
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

- [ ] `semantic_profile_version = p3.c58.trade_structure_flow.v2.3`。
- [ ] confirmed_signal 必须包含 price_acceptance_score 和 residual_confirmation_score。
- [ ] residual 使用 z-score 或同单位回归残差。
- [ ] 状态机按优先级裁决，避免 squeeze confirmed 与 crowding failure 同时输出。
- [ ] 输出包含 5m / 15m / 1h 多周期结论。
- [ ] fast_signal 标记是否已被 15m 确认。
- [ ] 不重复解释 K 线形态，只解释交易结构。

## 关联任务

- P1-C55
- P2-C38
- P8-C30
- P9-C35
- P4.5-C39
- P5-C56
