# P1-C52 / BTC Adoption v2.3 派生指标、真实结算需求与 BTC response 准备

## 状态

DONE

## Phase

P1 数据源接入与采集层

## 背景

`btc_adoption` 需要从“链上活跃度越高越 bullish”的旧逻辑，升级为“链上真实采用度是否确认、削弱或反证 BTC 当前 4h-7d 趋势”的 v2.3 模块。

原始 `active_addresses`、`transaction_count`、`transfer_volume_adjusted_usd`、`btc_hashrate`、Lightning capacity/node/channel 等字段保留，但不能直接作为方向信号。P1 需要先准备 activity、settlement、fee/mempool、security、lightning 与 BTC response 的派生指标。

专业依据：
- 普通地址数不能直接等同真实用户，entity-adjusted 指标更适合衡量真实经济交换。
- adjusted transfer value / NVT 更适合作为链上真实结算需求 proxy。
- fee/mempool 适合 0h-24h 快速预警，但必须区分健康需求升温与拥堵摩擦。
- hashrate/hashprice 是安全性与矿工压力 regime，不应直接触发短线方向。

## 目标

为 `p3.c54.btc_adoption.v2.3` 准备可消费的派生指标，让下游可以区分：

```text
fast_layer: 0h-24h 链上压力与价格响应
core_layer: 1d-7d 真实结算需求与采用度确认
regime_layer: 14d-90d 网络安全、矿工压力与 L2 背景
```

## 范围

### Activity

```text
active_entities_or_addresses_z_30d
active_entities_or_addresses_z_60d
active_entities_or_addresses_change_7d_pct
transaction_count_z_30d
transaction_count_z_60d
transaction_count_change_7d_pct
tx_per_active_entity
tx_per_active_entity_z_60d
activity_spike_flag
```

### Settlement

```text
transfer_volume_adjusted_usd_z_30d
transfer_volume_adjusted_usd_z_60d
transfer_volume_adjusted_usd_change_7d_pct
transfer_volume_per_tx
transfer_volume_per_active_entity
settlement_velocity_z_60d
nvt_proxy
nvt_proxy_z_180d
nvt_proxy_change_7d
```

### Fees / Mempool

```text
avg_fee_rate_1h
avg_fee_rate_24h
mempool_min_fee_rate
mempool_tx_count
mempool_vsize
fee_pressure_z_30d
fee_pressure_z_60d
fees_vs_reward_pct
congestion_without_settlement_flag
```

### Security

```text
hashrate_14d_ma
hashrate_14d_ma_change_7d_pct
hashrate_z_90d
hashprice_z_90d
miner_revenue_z_90d
miner_security_pressure_proxy
```

### Lightning / Network

```text
lightning_capacity_change_30d_pct
lightning_node_count_change_30d_pct
lightning_channel_count_change_30d_pct
lightning_capacity_per_channel
lightning_public_network_health_score
bitcoin_reachable_nodes_change_30d_pct
```

### BTC Response

```text
btc_return_4h
btc_return_24h
btc_return_3d
btc_return_7d
adoption_expected_return_24h
adoption_residual_24h
adoption_residual_z_90d
price_acceptance_score
```

## 关键公式

```text
nvt_proxy = btc_market_cap / transfer_volume_adjusted_usd
btc_market_cap = btc_price * btc_supply_current
```

```text
activity_quality_score_basis =
  0.35 * active_entities_or_addresses_z_60d
+ 0.30 * transaction_count_z_60d
+ 0.35 * transfer_volume_adjusted_usd_z_60d
```

```text
settlement_demand_score_basis =
  0.45 * transfer_volume_adjusted_usd_z_60d
+ 0.35 * (-nvt_proxy_change_7d_z)
+ 0.20 * settlement_velocity_z_60d
```

无足够回归样本时：

```text
adoption_expected_return_24h =
  0.35 * settlement_demand_score
+ 0.25 * activity_impulse_score
+ 0.20 * fee_mempool_score
+ 0.20 * nvt_improvement_score
```

## 数据质量规则

```text
if active address source is raw address-count only:
  proxy_flags += ["raw_address_count_not_entity_adjusted"]
  activity_quality_score_basis *= 0.65

if transfer_volume_adjusted_usd missing:
  disable settlement_demand_confirmed
  data_quality_flags += ["transfer_volume_adjusted_usd_missing"]

if transaction_count_z_60d >= 2 and transfer_volume_adjusted_usd_z_60d <= 0:
  activity_spike_flag = true

if fee/mempool data stale > 30m:
  disable fast fee signal

if fee/mempool data stale > 2h:
  disable fee_mempool_score

if adoption_residual sample < 90d:
  use rule-based fallback
  data_quality_flags += ["adoption_residual_fallback"]
```

## DoD

- [ ] 上述派生指标可写入 SQLite，并被 P2/P3 消费。
- [ ] 原始 level 指标保留为 context，不破坏现有数据源。
- [ ] `nvt_proxy`、`nvt_proxy_z_180d`、`nvt_proxy_change_7d` 可输出。
- [ ] fee/mempool stale 与 congestion flags 可输出。
- [ ] `adoption_expected_return_24h`、`adoption_residual_24h`、`adoption_residual_z_90d` 可输出。
- [ ] raw address / adjusted transfer / residual fallback 的 proxy 与 data quality flags 可输出。
- [ ] P1 采集、SQLite 持久化与历史窗口测试通过。

## 关联任务

- P2-C35
- P3-C50
- P8-C27
- P9-C32
