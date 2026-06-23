# P2-C37 / Kline Orderflow v2.2 registry context-only 与主动流接受度治理

## 状态

DONE

## Phase

P2 Radar 指标与模块层

## 背景

`kline_orderflow v2.2` 必须避免把 OHLCV、成交量、taker buy ratio 单独解释为 BTC 方向。P2 Registry 需要把原始 level 降级为 context，把真正参与方向判断的字段限定为趋势斜率、主动流接受度、VWAP 接受度、range break、false breakout/breakdown 和 residual。

## 原始字段降级

```text
btc_open
btc_high
btc_low
btc_close
btc_volume
btc_quote_volume
btc_taker_buy_volume
btc_taker_buy_quote_volume
btc_number_of_trades
```

## 方向参与字段

```text
slope_tstat_1h
slope_acceleration_15m
return_5m
return_15m
return_1h
taker_imbalance_z_20
taker_imbalance_z_60
taker_imbalance_accel_3
taker_imbalance_persistence_5
flow_price_acceptance_5m
flow_price_acceptance_15m
price_vs_vwap_15m_z
price_vs_vwap_1h_z
price_vs_vwap_4h_z
vwap_acceptance_duration_1m
micro_range_breakout_15m
local_range_breakout_1h
major_range_breakout_4h
false_breakout_score
false_breakdown_score
orderflow_residual_z_60
orderflow_residual_z_180
```

## Registry 语义规则

```text
taker_buy_ratio 高:
  不直接 bullish，只能作为 aggressor_flow context

taker_sell_ratio 高:
  不直接 bearish，只能作为 aggressor_flow context

flow_price_acceptance:
  可参与方向，因为它已经包含价格响应

false_breakout / false_breakdown:
  优先级高于普通 breakout / breakdown
```

## DoD

- [ ] 原始 OHLCV / taker level 字段不再直接给 bullish/bearish 方向。
- [ ] `flow_price_acceptance_*`、VWAP acceptance、range break、residual 字段进入 v2.2 方向规则。
- [ ] false breakout / false breakdown 字段具备高优先级或反证角色。
- [ ] Registry 输出可被 P3-C52 消费。
- [ ] P2 相关单元测试和 radar registry 测试通过。

## 关联任务

- P1-C54
- P3-C52
- P9-C34
