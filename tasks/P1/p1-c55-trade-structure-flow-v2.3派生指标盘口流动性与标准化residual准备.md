# P1-C55 / Trade Structure Flow v2.3 派生指标、盘口流动性与标准化 residual 准备

## 状态

DONE

## Phase

P1 数据源接入与采集层

## 背景

`trade_structure_flow` 需要从成交量、taker ratio、funding、OI、清算单因子，升级为 `p3.c58.trade_structure_flow.v2.3` 的交易结构确认/反证模块。核心不是判断某个交易所指标本身是否 bullish，而是判断盘口流动性、主动流、spot/perp lead、杠杆和清算后的 BTC price acceptance 是否共同确认或反证趋势。

## 目标

准备 P2/P3 可消费的 v2.3 派生指标：

```text
micro liquidity: spread / depth / liquidity gap
aggressive flow: 5m / 15m 主动成交突变与吸收/衰竭
spot_perp_lead: 现货主导还是合约主导
leverage: OI / funding / basis 的参与质量
liquidation_response: 清算后 follow-through 或 absorption
standardized_residual: return z-score 与 structure pressure z-score 同单位 residual
```

## 范围

### Fast Micro Layer

```text
best_bid
best_ask
mid_price
bid_ask_spread_bps
depth_bid_10bps
depth_ask_10bps
depth_bid_25bps
depth_ask_25bps
depth_bid_50bps
depth_ask_50bps
depth_bid_100bps
depth_ask_100bps
depth_imbalance_10bps
depth_imbalance_25bps
depth_imbalance_50bps
depth_imbalance_100bps
spread_z_5m
spread_z_15m
depth_thinning_z_5m
depth_thinning_z_15m
book_refill_speed
book_decay_speed
liquidity_gap_score
```

### Aggressive Flow Layer

```text
agg_buy_volume_5m
agg_sell_volume_5m
agg_flow_delta_5m
agg_flow_delta_z_5m
agg_buy_volume_15m
agg_sell_volume_15m
agg_flow_delta_15m
agg_flow_delta_z_15m
taker_buy_sell_ratio_5m
taker_buy_sell_ratio_15m
taker_flow_persistence_5m
taker_flow_persistence_15m
price_impact_per_1m_buy
price_impact_per_1m_sell
flow_absorption_score
flow_exhaustion_score
```

### Spot / Perp Lead Layer

```text
spot_volume_z_30d
perp_volume_z_30d
spot_perp_volume_ratio_z_60d
spot_price_lead_5m
perp_price_lead_5m
spot_perp_basis_z_60d
spot_led_score
perp_led_score
volume_quality_score
```

### Leverage / Liquidation / Residual

```text
open_interest_change_15m_pct
open_interest_change_1h_pct
open_interest_change_4h_pct
open_interest_z_60d
funding_rate_z_60d
funding_acceleration_24h
basis_z_60d
basis_change_24h
leverage_participation_score
leverage_crowding_risk_score
liquidation_long_z_30d
liquidation_short_z_30d
liquidation_imbalance
liquidation_total_z_30d
post_liquidation_return_5m
post_liquidation_return_15m
post_liquidation_recovery_1h
liquidation_followthrough_score
liquidation_absorption_score
liquidation_cascade_score
squeeze_failure_score
btc_return_z_5m
btc_return_z_15m
btc_return_z_1h
structure_pressure_z
expected_return_z
trade_structure_residual_z
```

## 数据质量规则

```text
if orderbook data stale > 10s:
  disable micro_turn signals
  confidence_score -= 10

if orderbook data stale > 30s:
  disable liquidity_directional_score
  confidence_score -= 15

if liquidation source == binance_forceOrder_snapshot:
  liquidation cannot trigger confirmed_signal alone
  data_quality_flags += ["liquidation_snapshot_only"]

if aggTrade missing:
  aggressive_flow_score = 0
  signal_stage max = early_warning
```

## DoD

- [ ] P1 能输出 v2.3 派生指标并写入 SQLite。
- [ ] residual 使用 return z-score 与 structure pressure z-score，不能 score 与 return 直接相减。
- [ ] orderbook 缺失时可降级为 spread/volume proxy，不阻塞模块。
- [ ] liquidation snapshot 只作为 context/fast evidence，不能单独 confirmed。
- [ ] 5m / 15m / 1h 多周期 BTC response 可被 P3 消费。
- [ ] P1 采集、SQLite 持久化与历史窗口测试通过。

## 关联任务

- P2-C38
- P3-C53
- P8-C30
- P9-C35
