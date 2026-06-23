# P2-C35 / BTC Adoption v2.3 Registry 真实采用度与 context-only 治理

## 状态

DONE

## Phase

P2 Radar 指标与模块层

## 背景

`btc_adoption` 旧版 registry 容易把 `active_addresses`、`transaction_count`、`btc_hashrate`、Lightning level 等慢变量或噪音变量直接解释成 bullish。v2.3 需要把原始 level 降级为 context，把真正参与状态机的字段切换为变化率、z-score、NVT、fee/mempool、BTC response residual。

## 目标

将 `btc_adoption` registry 升级为 `p3.c54.btc_adoption.v2.3` 可消费的指标角色体系：

```text
raw level -> context_only / composite_only
derived impulse -> directional candidate
fee/mempool -> fast warning context
hashrate/hashprice -> regime context
adoption_residual -> btc response veto
```

## 指标角色调整

### 原始 level 降级

```text
active_addresses              -> context_only
transaction_count             -> context_only
transfer_volume_adjusted_usd  -> context_only
btc_hashrate                  -> context_only
hashrate_90d_ehs              -> context_only
lightning_capacity_btc        -> context_only
lightning_node_count          -> context_only
lightning_channel_count       -> context_only
bitcoin_reachable_nodes       -> context_only
```

这些指标：

```text
affects_signal = false
driver_eligible = false
role = adoption_context / network_context / l2_context
```

### 参与状态机的字段

```text
active_entities_or_addresses_z_60d
transaction_count_z_60d
transfer_volume_adjusted_usd_z_60d
transfer_volume_adjusted_usd_change_7d_pct
nvt_proxy_change_7d
nvt_proxy_z_180d
fee_pressure_z_60d
mempool_vsize_z_30d
hashrate_14d_ma_change_7d_pct
hashprice_z_90d
adoption_residual_z_90d
btc_return_24h
```

### 语义 role

```text
activity_quality
settlement_demand
nvt_improvement
fee_mempool_pressure
network_security_context
miner_pressure_context
l2_adoption_context
btc_response_veto
data_quality_context
```

## 边界规则

```text
active_addresses / transaction_count 不允许单独触发 confirmed_signal
hashrate / Lightning level 不允许直接拉 24h module_direction
fee_pressure 高不直接 bullish，必须结合 settlement 和 btc_response
adoption_residual_z_90d 可作为接受/拒绝的 veto 字段
```

## DoD

- [ ] `btc_adoption` 原始 level 全部改为 context/composite 语义。
- [ ] v2.3 派生指标注册到 registry，并拥有明确 role、horizon、weight。
- [ ] `adoption_residual_z_90d` 作为 btc_response_veto 可被 P3 消费。
- [ ] fee/mempool、security、lightning 的 role 不混入硬方向。
- [ ] registry 测试和 radar 构建测试通过。

## 关联任务

- P1-C52
- P3-C50
- P8-C27
- P9-C32
