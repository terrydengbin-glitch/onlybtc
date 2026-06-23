# P1-C54 / Kline Orderflow v2.2 派生指标、fast sensing 与主动流接受度准备

## 状态

DONE

## Phase

P1 数据源接入与采集层

## 背景

`kline_orderflow` 需要从旧版 K 线/量价结构评分，升级为 `p3.c57.kline_orderflow.v2.2` 的短周期趋势感应模块。核心不是判断 OHLCV、放量或 taker buy ratio 本身是否 bullish，而是判断主动流是否被 BTC 价格结构、VWAP 和 residual 接受。

## 目标

准备可供 P2/P3 消费的派生指标：

```text
fast sensing: 1m/3m/5m 捕捉早期变盘
confirmation: 15m/1h/4h 确认趋势结构
rejection: false breakout / false breakdown / absorption / exhaustion
volatility adaptive: low_vol / normal_vol / high_vol / shock_vol
```

## 范围

### 原始 Binance Kline 字段

```text
open
high
low
close
volume
quote_volume
number_of_trades
taker_buy_volume
taker_buy_quote_volume
```

### Fast Bucket / 可选实时输入

```text
current_kline_unclosed
aggtrade_bucket_1s
aggtrade_bucket_5s
depth_imbalance_optional
```

如果暂时无法接入 `aggTrade` / depth，则使用 kline taker 字段降级，不阻塞模块。

### 核心派生指标

```text
return_1m
return_3m
return_5m
return_15m
return_1h
return_4h
slope_tstat_1h
slope_acceleration_15m
realized_vol_1h
realized_vol_4h
atr_14_15m
volatility_regime
taker_delta
taker_imbalance_z_20
taker_imbalance_z_60
taker_imbalance_accel_3
taker_imbalance_persistence_5
flow_price_acceptance_5m
flow_price_acceptance_15m
vwap_15m
vwap_1h
vwap_4h
price_vs_vwap_15m_z
price_vs_vwap_1h_z
price_vs_vwap_4h_z
vwap_acceptance_duration_1m
micro_range_high_15m
micro_range_low_15m
local_range_high_1h
local_range_low_1h
major_range_high_4h
major_range_low_4h
false_breakout_score
false_breakdown_score
orderflow_expected_return_1h
orderflow_residual_1h
orderflow_residual_z_60
orderflow_residual_z_180
```

## 数据质量规则

```text
if latest kline stale > 2 intervals:
  disable confirmed_signal inputs
  data_quality_flags += ["kline_data_stale"]

if taker_buy_volume missing:
  disable aggressor_flow_score
  data_quality_flags += ["taker_volume_missing"]

if orderbook depth unavailable:
  proxy_flags += ["orderbook_depth_missing_using_kline_taker_proxy"]
```

## DoD

- [ ] v2.2 派生指标可写入 SQLite，并被 P2/P3 消费。
- [ ] 原始 OHLCV 与 taker 字段保留为 context，不直接触发方向。
- [ ] `flow_price_acceptance_5m/15m` 可稳定输出。
- [ ] `vwap_15m/1h/4h` 与 range 关键位可输出。
- [ ] `volatility_regime` 可输出，并覆盖 fallback 逻辑。
- [ ] taker volume 或 depth 缺失时模块降级，不报错。
- [ ] P1 采集、SQLite 持久化与历史窗口测试通过。

## 关联任务

- P2-C37
- P3-C52
- P8-C29
- P9-C34
